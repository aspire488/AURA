Goal:

Generate valid n8n v2.26.8 workflows.

Requirements:

* Use real n8n export schema.
* Do not invent metadata fields.
* Do not invent workflowMetaData.
* Do not invent triggerCount.
* Do not invent saveData.
* Do not invent forcedExit.
* Use actual exported workflow structure.
* Include node positions.
* Include valid connections.

Target Workflow:

AURA Service Monitor

Flow:

Schedule Trigger (every 1 minute)
↓
Execute Command

docker ps --format "{{.Names}}|{{.Status}}"

↓
Code Node

Parse service output into JSON

↓
Code Node

Evaluate:

* aura-redis
* aura-neo4j
* aura-chromadb
* aura-n8n

Output:

{
"status": "HEALTHY" | "DEGRADED",
"failedServices": [],
"timestamp": "ISO8601"
}

Return ONLY valid importable n8n workflow JSON.
