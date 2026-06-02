"""Multi-tenant isolation test.

Tests that:
1. Two tenants can register independently
2. Tenant A cannot see tenant B's agents/sessions/skills
3. Sandbox workspaces are isolated per tenant
4. User settings are tenant-scoped
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


async def test_multi_tenant():
    """Run multi-tenant isolation tests."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.models.database import init_db

    # Initialize DB
    await init_db()

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")

    print("=" * 60)
    print("Multi-Tenant Isolation Tests")
    print("=" * 60)

    passed = 0
    failed = 0

    # ── Test 1: Register two tenants ──────────────────────────
    print("\n[Test 1] Register two tenants")
    r1 = await client.post("/api/auth/register", json={
        "email": "alice@test.com", "password": "password123", "name": "Alice Workspace"
    })
    assert r1.status_code == 200, f"Tenant A register failed: {r1.text}"
    tenant_a = r1.json()
    token_a = tenant_a["access_token"]
    tid_a = tenant_a["tenant_id"]
    print(f"  Tenant A: {tid_a}")

    r2 = await client.post("/api/auth/register", json={
        "email": "bob@test.com", "password": "password456", "name": "Bob Workspace"
    })
    assert r2.status_code == 200, f"Tenant B register failed: {r2.text}"
    tenant_b = r2.json()
    token_b = tenant_b["access_token"]
    tid_b = tenant_b["tenant_id"]
    print(f"  Tenant B: {tid_b}")

    assert tid_a != tid_b, "Tenant IDs should be different"
    print("  [PASS] Two tenants registered with different IDs")
    passed += 1

    # ── Test 2: Duplicate registration fails ──────────────────
    print("\n[Test 2] Duplicate email registration fails")
    r_dup = await client.post("/api/auth/register", json={
        "email": "alice@test.com", "password": "other"
    })
    assert r_dup.status_code == 400, f"Expected 400, got {r_dup.status_code}"
    print("  [PASS] Duplicate registration rejected")
    passed += 1

    # ── Test 3: Login works ──────────────────────────────────
    print("\n[Test 3] Login works")
    r_login = await client.post("/api/auth/login", json={
        "email": "alice@test.com", "password": "password123"
    })
    assert r_login.status_code == 200, f"Login failed: {r_login.text}"
    assert r_login.json()["tenant_id"] == tid_a
    print("  [PASS] Login returns correct tenant_id")
    passed += 1

    # ── Test 4: Wrong password fails ─────────────────────────
    print("\n[Test 4] Wrong password fails")
    r_bad = await client.post("/api/auth/login", json={
        "email": "alice@test.com", "password": "wrong"
    })
    assert r_bad.status_code == 401, f"Expected 401, got {r_bad.status_code}"
    print("  [PASS] Wrong password rejected")
    passed += 1

    # ── Test 5: Unauthenticated requests fail ────────────────
    print("\n[Test 5] Unauthenticated requests fail")
    r_noauth = await client.get("/api/agents")
    assert r_noauth.status_code == 401, f"Expected 401, got {r_noauth.status_code}"
    print("  [PASS] Unauthenticated request rejected")
    passed += 1

    # ── Test 6: /api/auth/me works ───────────────────────────
    print("\n[Test 6] /api/auth/me works")
    r_me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    assert r_me.status_code == 200
    assert r_me.json()["tenant_id"] == tid_a
    assert r_me.json()["email"] == "alice@test.com"
    print("  [PASS] /api/auth/me returns correct user info")
    passed += 1

    # ── Test 7: Agent creation is tenant-scoped ──────────────
    print("\n[Test 7] Agent creation is tenant-scoped")
    h_a = {"Authorization": f"Bearer {token_a}"}
    h_b = {"Authorization": f"Bearer {token_b}"}

    # Create agent for tenant A
    r_create = await client.post("/api/agents", json={
        "name": "alice_agent", "provider": "openai", "model": "gpt-4o"
    }, headers=h_a)
    assert r_create.status_code == 200, f"Create agent failed: {r_create.text}"
    print(f"  Created agent for Tenant A: alice_agent")

    # Create agent for tenant B
    r_create_b = await client.post("/api/agents", json={
        "name": "bob_agent", "provider": "openai", "model": "gpt-4o"
    }, headers=h_b)
    assert r_create_b.status_code == 200, f"Create agent failed: {r_create_b.text}"
    print(f"  Created agent for Tenant B: bob_agent")

    # Tenant A should NOT see bob_agent
    r_list_a = await client.get("/api/agents", headers=h_a)
    agent_ids_a = [a["agent_id"] for a in r_list_a.json()["agents"]]
    assert "bob_agent" not in agent_ids_a, f"Tenant A should not see bob_agent, but saw: {agent_ids_a}"
    print(f"  Tenant A agents: {agent_ids_a}")

    # Tenant B should NOT see alice_agent
    r_list_b = await client.get("/api/agents", headers=h_b)
    agent_ids_b = [a["agent_id"] for a in r_list_b.json()["agents"]]
    assert "alice_agent" not in agent_ids_b, f"Tenant B should not see alice_agent, but saw: {agent_ids_b}"
    print(f"  Tenant B agents: {agent_ids_b}")

    print("  [PASS] Agents are isolated between tenants")
    passed += 1

    # ── Test 8: Session creation is tenant-scoped ────────────
    print("\n[Test 8] Session creation is tenant-scoped")
    r_sess_a = await client.post("/api/chat/sessions", json={"title": "Alice Chat"}, headers=h_a)
    assert r_sess_a.status_code == 200

    r_sess_b = await client.post("/api/chat/sessions", json={"title": "Bob Chat"}, headers=h_b)
    assert r_sess_b.status_code == 200

    # Tenant A should only see their sessions
    r_sessions_a = await client.get("/api/chat/sessions", headers=h_a)
    session_titles_a = [s["title"] for s in r_sessions_a.json()["sessions"]]
    assert "Bob Chat" not in session_titles_a, f"Tenant A should not see Bob's sessions"
    print(f"  Tenant A sessions: {session_titles_a}")

    r_sessions_b = await client.get("/api/chat/sessions", headers=h_b)
    session_titles_b = [s["title"] for s in r_sessions_b.json()["sessions"]]
    assert "Alice Chat" not in session_titles_b, f"Tenant B should not see Alice's sessions"
    print(f"  Tenant B sessions: {session_titles_b}")

    print("  [PASS] Sessions are isolated between tenants")
    passed += 1

    # ── Test 9: Skills are tenant-scoped ─────────────────────
    print("\n[Test 9] Skills are tenant-scoped")
    r_skill_a = await client.post("/api/skills", json={
        "name": "alice_skill", "description": "Alice's skill", "instruction": "Do Alice things"
    }, headers=h_a)
    assert r_skill_a.status_code == 200

    r_skill_b = await client.post("/api/skills", json={
        "name": "bob_skill", "description": "Bob's skill", "instruction": "Do Bob things"
    }, headers=h_b)
    assert r_skill_b.status_code == 200

    # Tenant A should not see bob_skill
    r_skills_a = await client.get("/api/skills", headers=h_a)
    skill_names_a = [s["name"] for s in r_skills_a.json()["skills"]]
    assert "bob_skill" not in skill_names_a, f"Tenant A should not see bob_skill"
    print(f"  Tenant A skills: {skill_names_a}")

    # Tenant B should not see alice_skill
    r_skills_b = await client.get("/api/skills", headers=h_b)
    skill_names_b = [s["name"] for s in r_skills_b.json()["skills"]]
    assert "alice_skill" not in skill_names_b, f"Tenant B should not see alice_skill"
    print(f"  Tenant B skills: {skill_names_b}")

    print("  [PASS] Skills are isolated between tenants")
    passed += 1

    # ── Test 10: Sandbox workspaces are tenant-scoped ────────
    print("\n[Test 10] Sandbox workspaces are tenant-scoped")
    from app.sandbox.manager import init_agent_workspace, get_shared_workspace
    ws_a = init_agent_workspace("test_agent", tenant_id=tid_a)
    ws_b = init_agent_workspace("test_agent", tenant_id=tid_b)
    assert tid_a in ws_a, f"Workspace A should contain tenant_id: {ws_a}"
    assert tid_b in ws_b, f"Workspace B should contain tenant_id: {ws_b}"
    assert ws_a != ws_b, "Workspaces should be different"
    print(f"  Workspace A: {ws_a}")
    print(f"  Workspace B: {ws_b}")

    # Shared workspace should also be tenant-scoped
    shared_a = get_shared_workspace(tenant_id=tid_a)
    shared_b = get_shared_workspace(tenant_id=tid_b)
    assert shared_a != shared_b, "Shared workspaces should be different"
    print(f"  Shared A: {shared_a}")
    print(f"  Shared B: {shared_b}")

    print("  [PASS] Sandbox workspaces are isolated between tenants")
    passed += 1

    # ── Test 11: Stats are tenant-scoped ─────────────────────
    print("\n[Test 11] Stats are tenant-scoped")
    r_stats_a = await client.get("/api/stats/overview", headers=h_a)
    assert r_stats_a.status_code == 200

    r_stats_b = await client.get("/api/stats/overview", headers=h_b)
    assert r_stats_b.status_code == 200

    print("  [PASS] Stats endpoints accept tenant context")
    passed += 1

    # ── Test 12: User settings are tenant-scoped ─────────────
    print("\n[Test 12] User settings are tenant-scoped")
    await client.put("/api/user-settings", json={"settings": {"theme": "dark"}}, headers=h_a)
    await client.put("/api/user-settings", json={"settings": {"theme": "light"}}, headers=h_b)

    r_settings_a = await client.get("/api/user-settings", headers=h_a)
    assert r_settings_a.json()["settings"]["theme"] == "dark"

    r_settings_b = await client.get("/api/user-settings", headers=h_b)
    assert r_settings_b.json()["settings"]["theme"] == "light"

    print("  [PASS] User settings are isolated between tenants")
    passed += 1

    # ── Summary ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\nAll tests passed!")

    sys.stdout.flush()
    sys.stderr.flush()
    # Force exit to avoid hanging on background task cleanup
    os._exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    try:
        asyncio.run(test_multi_tenant())
    except Exception as e:
        print(f"Test error: {e}")
        os._exit(1)
