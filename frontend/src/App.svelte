<script>
  import LogList from "./LogList.svelte";
  import Wall from "./Wall.svelte";

  let session = null;
  let view = "logs";
  let loginUser = "surveyor";
  let loginPass = "surv123456";
  let error = "";
  let loading = false;

  $: isWriter = session?.role === "writer";

  function authHeaders() {
    return session ? { Authorization: "Bearer " + session.token } : {};
  }

  async function login() {
    error = "";
    loading = true;
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: loginUser, password: loginPass }),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || "登录失败";
        return;
      }
      session = { token: data.access_token, username: data.username, role: data.role };
      localStorage.setItem("tunnel_session", JSON.stringify(session));
    } catch {
      error = "无法连接接口";
    } finally {
      loading = false;
    }
  }

  function logout() {
    session = null;
    view = "logs";
    localStorage.removeItem("tunnel_session");
  }

  const raw = localStorage.getItem("tunnel_session");
  if (raw) {
    try {
      session = JSON.parse(raw);
    } catch {
      localStorage.removeItem("tunnel_session");
    }
  }
</script>

<style>
  :global(body) {
    margin: 0;
    font-family: "Segoe UI", system-ui, sans-serif;
    background: #1c1917;
    color: #f5f5f4;
  }
  :global(label) { display: block; font-size: 0.85rem; color: #d6d3d1; margin-bottom: 0.25rem; }
  :global(input) {
    width: 100%; box-sizing: border-box; padding: 0.5rem 0.65rem; border-radius: 6px;
    border: 1px solid #57534e; background: #0c0a09; color: #fafaf9; margin-bottom: 0.75rem;
  }
  :global(button) {
    cursor: pointer; padding: 0.5rem 1rem; border: none; border-radius: 6px;
    background: #d97706; color: #fff; font-weight: 600;
  }
  :global(button:disabled) { opacity: 0.5; cursor: not-allowed; }
  :global(button.secondary) { background: #57534e; }
  :global(.err) { color: #fb7185; }
  :global(table) { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  :global(th), :global(td) { text-align: left; padding: 0.45rem; border-bottom: 1px solid #44403c; }
  :global(.tag) { padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.8rem; }
  :global(.tag.ok) { background: #14532d; color: #86efac; }
  :global(.tag.bad) { background: #7f1d1d; color: #fca5a5; }
  :global(.tag.pending) { background: #713f12; color: #fde68a; }
  :global(section.card) {
    background: #292524; border: 1px solid #44403c; border-radius: 8px;
    padding: 1rem 1.25rem; margin-bottom: 1rem;
  }

  header {
    display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
    max-width: 1100px; margin: 0 auto; padding: 1rem 1.5rem 0;
  }
  .brand { color: #fbbf24; font-weight: 700; font-size: 1.25rem; }
  nav { display: flex; gap: 0.5rem; }
  nav button {
    background: transparent; color: #d6d3d1; border: 1px solid #57534e;
  }
  nav button.active { background: #d97706; border-color: #d97706; color: #fff; }
  .who { margin-left: auto; color: #a8a29e; font-size: 0.9rem; }
  main { max-width: 1100px; margin: 0 auto; padding: 1rem 1.5rem 1.5rem; }
  h1 { color: #fbbf24; margin: 0 0 0.25rem; }
  .sub { color: #a8a29e; margin-bottom: 1.25rem; }
</style>

{#if !session}
  <main>
    <h1>隧道收敛测缝台</h1>
    <p class="sub">测量员提交桩号与收敛毫米值，接口进程内线程认领后出结论。登录框已预填可写账号 surveyor / surv123456。</p>
    <section class="card">
      <label>用户名</label>
      <input bind:value={loginUser} autocomplete="off" />
      <label>密码</label>
      <input type="password" bind:value={loginPass} autocomplete="off" />
      <button disabled={loading} on:click={login}>登录</button>
      {#if error}<p class="err">{error}</p>{/if}
    </section>
  </main>
{:else}
  <header>
    <span class="brand">隧道收敛测缝台</span>
    <nav>
      <button class:active={view === "logs"} on:click={() => (view = "logs")}>记录列表</button>
      <button class:active={view === "wall"} on:click={() => (view = "wall")}>色块墙</button>
    </nav>
    <span class="who">{session.username} · {isWriter ? "测量员" : "巡检岗（只读）"}</span>
    <button class="secondary" on:click={logout}>退出</button>
  </header>
  <main>
    {#if view === "logs"}
      <LogList {session} {authHeaders} onunauth={logout} />
    {:else}
      <Wall {session} {authHeaders} onunauth={logout} />
    {/if}
  </main>
{/if}
