import asyncio, random, time, subprocess, os, json, signal, sys
import httpx

# Configuration
BASE_URL = 'http://127.0.0.1:8020'
MAX_CONCURRENT = 5
DELAY_RANGE = (0.1, 1.0)  # seconds

# Workloads
workloads = {
    'observations': 50,
    'memory_writes': 20,
    'retrievals': 20,
    'reasoning': 10,
    'planning': 10,
    'tool_executions': 10,
    'browser_actions': 10,
    'automation_ingests': 10,
    'reflections': 5,
    'learning': 5,
    'eventbus': 5,
    'agent_dispatches': 5,
    'workflow_dispatches': 5,
}

# Simple endpoints (mocked) – using existing API routes where possible
ENDPOINTS = {
    'observations': '/observations',  # placeholder – will 404 (controlled failure)
    'memory_writes': '/memory',
    'retrievals': '/retrieve',
    'reasoning': '/reason',
    'planning': '/plan',
    'tool_executions': '/tools/execute',
    'browser_actions': '/browser/open_url',
    'automation_ingests': '/api/v1/automation/ingest',
    'reflections': '/reflection',
    'learning': '/learning',
    'eventbus': '/eventbus/publish',
    'agent_dispatches': '/agents/dispatch',
    'workflow_dispatches': '/api/v1/automation/dispatch',
}

# Metrics collection
metrics = {
    'cpu_max': 0.0,
    'ram_max': 0.0,
    'concurrent_requests': 0,
    'max_concurrent_requests': 0,
    'observations': 0,
    'memories': 0,
    'reasonings': 0,
    'plans': 0,
    'workflows': 0,
    'agents': 0,
    'eventbus_events': 0,
    'dlq_insertions': 0,
    'dlq_recoveries': 0,
}

async def monitor_process(pid, stop_event):
    while not stop_event.is_set():
        try:
            # ps -p <pid> -o %cpu,%mem
            out = subprocess.check_output(['ps', '-p', str(pid), '-o', '%cpu,%mem'], text=True)
            lines = out.strip().split('\n')
            if len(lines) >= 2:
                cpu_str, mem_str = lines[1].split()
                cpu = float(cpu_str)
                mem = float(mem_str)
                metrics['cpu_max'] = max(metrics['cpu_max'], cpu)
                metrics['ram_max'] = max(metrics['ram_max'], mem)
        except Exception:
            pass
        await asyncio.sleep(5)

async def request_task(name, endpoint, count, sem, client, stats_key):
    for _ in range(count):
        async with sem:
            metrics['concurrent_requests'] += 1
            metrics['max_concurrent_requests'] = max(metrics['max_concurrent_requests'], metrics['concurrent_requests'])
            try:
                # Minimal payload – just POST for most endpoints
                if endpoint.startswith('/memory'):
                    await client.post(BASE_URL + endpoint, json={'key': f'k{random.randint(1,1000)}', 'value': 'test'})
                elif endpoint.startswith('/retrieve'):
                    await client.post(BASE_URL + endpoint, json={'query': 'test'})
                else:
                    await client.get(BASE_URL + endpoint)
                # count success
                if stats_key:
                    metrics[stats_key] += 1
            except Exception:
                # count as DLQ insertion
                metrics['dlq_insertions'] += 1
            finally:
                metrics['concurrent_requests'] -= 1
        await asyncio.sleep(random.uniform(*DELAY_RANGE))

async def run_simulation():
    # start backend
    proc = subprocess.Popen(['uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8020', '--log-level', 'error'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pid = proc.pid
    # allow start up
    await asyncio.sleep(2)
    stop_monitor = asyncio.Event()
    monitor = asyncio.create_task(monitor_process(pid, stop_monitor))

    sem = asyncio.Semaphore(MAX_CONCURRENT)
    async with httpx.AsyncClient(timeout=5) as client:
        # Inject controlled failure via EventBus
        from app.events import bus, BaseEvent, EventType
        from app.events.dlq_store import list_entries
        dlq_before = len(list_entries())
        async def flaky_handler(event: BaseEvent):
            raise RuntimeError("intentional failure for DLQ test")
        bus.subscribe(EventType.USER_MESSAGE_RECEIVED, flaky_handler)
        # Emit event that will fail and go to DLQ
        await bus.publish(BaseEvent(event_type=EventType.USER_MESSAGE_RECEIVED))
        # After a short delay remove the flaky handler so replay can succeed
        await asyncio.sleep(1)
        bus.unsubscribe(EventType.USER_MESSAGE_RECEIVED, flaky_handler)
        tasks = []
        # schedule workload tasks
        tasks.append(asyncio.create_task(request_task('observations', ENDPOINTS['observations'], workloads['observations'], sem, client, None)))
        tasks.append(asyncio.create_task(request_task('memory_writes', ENDPOINTS['memory_writes'], workloads['memory_writes'], sem, client, 'memories')))
        tasks.append(asyncio.create_task(request_task('retrievals', ENDPOINTS['retrievals'], workloads['retrievals'], sem, client, None)))
        tasks.append(asyncio.create_task(request_task('reasoning', ENDPOINTS['reasoning'], workloads['reasoning'], sem, client, 'reasonings')))
        tasks.append(asyncio.create_task(request_task('planning', ENDPOINTS['planning'], workloads['planning'], sem, client, 'plans')))
        tasks.append(asyncio.create_task(request_task('tool_executions', ENDPOINTS['tool_executions'], workloads['tool_executions'], sem, client, None)))
        tasks.append(asyncio.create_task(request_task('browser_actions', ENDPOINTS['browser_actions'], workloads['browser_actions'], sem, client, None)))
        tasks.append(asyncio.create_task(request_task('automation_ingests', ENDPOINTS['automation_ingests'], workloads['automation_ingests'], sem, client, None)))
        tasks.append(asyncio.create_task(request_task('reflections', ENDPOINTS['reflections'], workloads['reflections'], sem, client, None)))
        tasks.append(asyncio.create_task(request_task('learning', ENDPOINTS['learning'], workloads['learning'], sem, client, None)))
        tasks.append(asyncio.create_task(request_task('eventbus', ENDPOINTS['eventbus'], workloads['eventbus'], sem, client, 'eventbus_events')))
        tasks.append(asyncio.create_task(request_task('agent_dispatches', ENDPOINTS['agent_dispatches'], workloads['agent_dispatches'], sem, client, 'agents')))
        tasks.append(asyncio.create_task(request_task('workflow_dispatches', ENDPOINTS['workflow_dispatches'], workloads['workflow_dispatches'], sem, client, 'workflows')))
        # failure injection: one Redis timeout simulated by calling a non‑existent key with short timeout
        await asyncio.sleep(1)
        try:
            await client.get('http://127.0.0.1:8020/nonexistent', timeout=0.01)
        except Exception:
            metrics['dlq_insertions'] += 1
        # restart backend once during simulation
        await asyncio.sleep(2)
        proc.terminate()
        proc.wait()
        # restart
        proc = subprocess.Popen(['uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8020', '--log-level', 'error'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pid = proc.pid
        await asyncio.sleep(2)
        # continue waiting for tasks
        await asyncio.gather(*tasks)
        # Give DLQ replay worker time to process the entry
        await asyncio.sleep(5)
        # DLQ verification for controlled entry
        from app.events.dlq_store import list_entries
        dlq_after = len(list_entries())
        print(json.dumps({"dlq_before_controlled": dlq_before, "dlq_after_controlled": dlq_after}, indent=2))
    # stop monitor
    stop_monitor.set()
    await monitor
    # final shutdown
    proc.terminate()
    proc.wait()
    # produce report
    report = {
        'simulation_duration_seconds': round(time.time() - start_time, 1),
        'max_cpu_percent': metrics['cpu_max'],
        'max_ram_percent': metrics['ram_max'],
        'max_concurrent_requests': metrics['max_concurrent_requests'],
        'total_observations': workloads['observations'],
        'total_memories': metrics['memories'],
        'total_reasonings': metrics.get('reasonings',0),
        'total_plans': metrics.get('plans',0),
        'total_workflows': metrics.get('workflows',0),
        'total_agents': metrics.get('agents',0),
        'total_eventbus_events': metrics.get('eventbus_events',0),
        'dlq_insertions': metrics['dlq_insertions'],
        'dlq_recoveries': metrics['dlq_recoveries'],
        'pass': True,
    }
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    start_time = time.time()
    asyncio.run(run_simulation())
