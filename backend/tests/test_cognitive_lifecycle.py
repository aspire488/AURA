


def test_full_aura_cognitive_lifecycle():
    async def run_test():
        # Ensure DB tables exist
        await world_store.initialize()

        # Insert a low‑confidence relation to trigger reflection
        from app.world.models import WorldRelation
        low_relation = WorldRelation(
            relation_id="reltest001",
            source_entity="entA",
            target_entity="entB",
            relation_type="likes",
            confidence=0.3,
        )
        await world_store.save_relation(low_relation)

        # Run reflection – ensure it completes without error
        
        await execute_system_reflection()

        # Run a simple KIO request that triggers a tool (time)
        await identity_store.initialize()
        # ponytail: stub continuity store to avoid DB tables
        async def _no_find_by_session(session_id: str):
            return None
        continuity_mod.continuity_store.find_by_session = _no_find_by_session
        async def _no_save(cont):
            return None
        continuity_mod.continuity_store.save = _no_save
        redis = RedisService()
        sessions = SessionManager(redis)
        kio = KIOAdapter(sessions=sessions)
        request = KIORequest(query="What time is it?", metadata={"user_alias": "test_user"})
        response = await kio.process_request(request)
        assert isinstance(response.answer, str) and response.answer.strip(), "KIO should return a non‑empty answer"

        # Verify identity was created

        ids = await identity_store.find_by_alias("test_user")
        assert ids, "Identity should be created for the user alias"
    asyncio.run(run_test())
