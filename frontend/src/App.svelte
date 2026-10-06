<script>
  let session = null;
  let page = "list";
  let logs = [];
  let sections = [];
  let loginUser = "surveyor";
  let loginPass = "surv123456";
  let chainage = "";
  let deltaMm = "";
  let error = "";
  let wallError = "";
  let loading = false;
  let editMode = false;
  let timer;
  let wallEl;
  let drag = null;

  $: isWriter = session?.role === "writer";

  function headers() {
    return session ? { Authorization: "Bearer " + session.token } : {};
  }

  async function refresh() {
    if (!session) return;
    const res = await fetch("/api/logs", { headers: headers() });
    if (res.status === 401) {
      logout();
      return;
    }
    if (res.ok) logs = await res.json();
  }

  async function loadSections() {
    if (!session) return;
    wallError = "";
    const res = await fetch("/api/sections", { headers: headers() });
    if (res.status === 401) {
      logout();
      return;
    }
    if (res.ok) {
      sections = await res.json();
    } else {
      wallError = "色块墙刷新失败";
    }
  }

  function tick() {
    if (page === "wall") {
      if (!drag) loadSections();
    } else {
      refresh();
    }
  }

  function startTimer() {
    if (timer) clearInterval(timer);
    timer = setInterval(tick, 2000);
  }

  function goto(p) {
    page = p;
    editMode = false;
    if (p === "wall") loadSections();
    else refresh();
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
      await refresh();
      startTimer();
    } catch {
      error = "无法连接接口";
    } finally {
      loading = false;
    }
  }

  function logout() {
    if (timer) clearInterval(timer);
    session = null;
    logs = [];
    sections = [];
    page = "list";
    editMode = false;
    localStorage.removeItem("tunnel_session");
  }

  async function submit() {
    error = "";
    loading = true;
    try {
      const res = await fetch("/api/logs", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers() },
        body: JSON.stringify({ chainage, delta_mm: Number(deltaMm) }),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || "提交失败";
        return;
      }
      chainage = "";
      deltaMm = "";
      await refresh();
    } catch {
      error = "提交时网络异常";
    } finally {
      loading = false;
    }
  }

  const clamp = (v) => Math.min(97, Math.max(0, v));

  function onBlockDown(e, s) {
    if (!editMode || !isWriter || !wallEl) return;
    e.preventDefault();
    drag = { chainage: s.chainage, rect: wallEl.getBoundingClientRect() };
    window.addEventListener("pointermove", onDragMove);
    window.addEventListener("pointerup", onDragUp, { once: true });
  }

  function onDragMove(e) {
    if (!drag) return;
    const x = clamp(((e.clientX - drag.rect.left) / drag.rect.width) * 100);
    const y = clamp(((e.clientY - drag.rect.top) / drag.rect.height) * 100);
    sections = sections.map((s) =>
      s.chainage === drag.chainage ? { ...s, x, y } : s
    );
  }

  async function onDragUp() {
    window.removeEventListener("pointermove", onDragMove);
    if (!drag) return;
    const s = sections.find((it) => it.chainage === drag.chainage);
    const target = drag.chainage;
    drag = null;
    if (!s) return;
    const res = await fetch("/api/sections/" + encodeURIComponent(target), {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...headers() },
      body: JSON.stringify({ x: s.x, y: s.y }),
    });
    if (!res.ok) {
      wallError = "坐标保存失败";
    }
    await loadSections();
  }

  const raw = localStorage.getItem("tunnel_session");
  if (raw) {
    try {
      session = JSON.parse(raw);
      refresh();
      startTimer();
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
  main { max-width: 960px; margin: 0 auto; padding: 1.5rem; }
  h1 { color: #fbbf24; margin: 0 0 0.25rem; }
  .sub { color: #a8a29e; margin-bottom: 1.25rem; }
  section {
    background: #292524; border: 1px solid #44403c; border-radius: 8px;
    padding: 1rem 1.25rem; margin-bottom: 1rem;
  }
  label { display: block; font-size: 0.85rem; color: #d6d3d1; margin-bottom: 0.25rem; }
  input {
    width: 100%; box-sizing: border-box; padding: 0.5rem 0.65rem; border-radius: 6px;
    border: 1px solid #57534e; background: #0c0a09; color: #fafaf9; margin-bottom: 0.75rem;
  }
  button {
    cursor: pointer; padding: 0.5rem 1rem; border: none; border-radius: 6px;
    background: #d97706; color: #fff; font-weight: 600;
  }
  button.secondary { background: #57534e; }
  .err { color: #fb7185; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th, td { text-align: left; padding: 0.45rem; border-bottom: 1px solid #44403c; }
  .tag { padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.8rem; }
  .ok { background: #14532d; color: #86efac; }
  .bad { background: #7f1d1d; color: #fca5a5; }
  .pending { background: #713f12; color: #fde68a; }

  header.topbar {
    display: flex; align-items: center; justify-content: space-between;
    gap: 0.75rem; padding: 0.6rem 1.25rem;
    background: #0c0a09; border-bottom: 1px solid #44403c;
  }
  .topbar .side { display: flex; align-items: center; gap: 0.5rem; min-width: 0; }
  .topbar .brand { color: #fbbf24; font-weight: 700; margin-right: 0.5rem; white-space: nowrap; }
  .topbar nav { display: flex; gap: 0.25rem; }
  .topbar nav button {
    background: transparent; color: #d6d3d1; font-weight: 600;
    border: 1px solid transparent; border-radius: 6px;
  }
  .topbar nav button.active { background: #292524; color: #fbbf24; border-color: #57534e; }
  .topbar button.editing { background: #b45309; }
  .topbar .who { color: #a8a29e; font-size: 0.85rem; white-space: nowrap; }

  .wall {
    position: relative; height: 460px; border-radius: 8px; overflow: hidden;
    background:
      linear-gradient(#292524 1px, transparent 1px) 0 0 / 100% 46px,
      linear-gradient(90deg, #292524 1px, transparent 1px) 0 0 / 46px 100%,
      #171412;
    border: 1px solid #44403c;
  }
  .block {
    position: absolute; transform: translate(-50%, -50%);
    min-width: 96px; padding: 0.5rem 0.6rem; border-radius: 8px;
    border: 1px solid #44403c; text-align: center; user-select: none;
    background: #44403c; color: #d6d3d1;
  }
  .block.green { background: #15803d; border-color: #22c55e; color: #ecfdf5; }
  .block.red { background: #b91c1c; border-color: #ef4444; color: #fef2f2; }
  .block .ch { font-weight: 700; font-size: 0.9rem; }
  .block .vd { font-size: 0.75rem; opacity: 0.85; margin-top: 0.15rem; }
  .wall.editing .block { cursor: grab; border-style: dashed; }
  .legend { display: flex; gap: 1rem; font-size: 0.8rem; color: #a8a29e; margin-top: 0.6rem; }
  .legend span::before {
    content: ""; display: inline-block; width: 0.7rem; height: 0.7rem;
    border-radius: 3px; margin-right: 0.3rem; vertical-align: -0.1rem;
  }
  .legend .lg-green::before { background: #15803d; }
  .legend .lg-red::before { background: #b91c1c; }
  .legend .lg-gray::before { background: #44403c; }
</style>

{#if session}
  <header class="topbar">
    <div class="side">
      {#if page === "wall" && isWriter}
        <button
          class:editing={editMode}
          on:click={() => (editMode = !editMode)}
        >{editMode ? "完成维护" : "维护坐标"}</button>
      {:else}
        <span class="brand">隧道收敛测缝台</span>
      {/if}
      <nav>
        <button class:active={page === "list"} on:click={() => goto("list")}>记录列表</button>
        <button class:active={page === "wall"} on:click={() => goto("wall")}>色块墙</button>
      </nav>
    </div>
    <div class="side">
      {#if page === "wall"}
        <button class="secondary" on:click={loadSections}>整面墙刷新</button>
      {/if}
      <span class="who">{session.username}（{isWriter ? "可提交" : "只读"}）</span>
      <button class="secondary" on:click={logout}>退出</button>
    </div>
  </header>
{/if}

<main>
  {#if !session}
    <h1>隧道收敛测缝台</h1>
    <p class="sub">测量员提交桩号与收敛毫米值，接口进程内线程认领后出结论。登录框已预填可写账号 surveyor / surv123456。</p>
    <section>
      <label>用户名</label>
      <input bind:value={loginUser} autocomplete="off" />
      <label>密码</label>
      <input type="password" bind:value={loginPass} autocomplete="off" />
      <button disabled={loading} on:click={login}>登录</button>
      {#if error}<p class="err">{error}</p>{/if}
    </section>
  {:else if page === "wall"}
    <h1>断面色块墙</h1>
    <p class="sub">
      色块取自接口返回的各断面最近一次办结结论；从未办结的断面保持灰色。
      {#if isWriter}点页眉「维护坐标」后可拖动色块调整位置。{:else}巡检岗只读，不能拖动也不能填报。{/if}
    </p>
    <div class="wall" class:editing={editMode && isWriter} bind:this={wallEl}>
      {#each sections as s (s.chainage)}
        <div
          class="block {s.verdict === '合格' ? 'green' : s.verdict === '超限' ? 'red' : ''}"
          style="left: {s.x}%; top: {s.y}%;"
          on:pointerdown={(e) => onBlockDown(e, s)}
        >
          <div class="ch">{s.chainage}</div>
          <div class="vd">{s.verdict ?? "未办结"}</div>
        </div>
      {/each}
    </div>
    <div class="legend">
      <span class="lg-green">合格</span>
      <span class="lg-red">超限</span>
      <span class="lg-gray">未办结</span>
    </div>
    {#if wallError}<p class="err">{wallError}</p>{/if}
  {:else}
    <h1>隧道收敛测缝台</h1>
    <p class="sub">已登录：{session.username}（{isWriter ? "可提交" : "只读"}）</p>
    <section>
      <button class="secondary" disabled={loading} on:click={refresh}>刷新列表</button>
    </section>
    {#if isWriter}
      <section>
        <label>里程桩号</label>
        <input placeholder="例如 K20+050" bind:value={chainage} />
        <label>收敛（毫米，可正可负）</label>
        <input type="number" step="0.1" bind:value={deltaMm} />
        <button disabled={loading} on:click={submit}>提交（进入待认领）</button>
        {#if error}<p class="err">{error}</p>{/if}
      </section>
    {/if}
    <section>
      <table>
        <thead>
          <tr><th>编号</th><th>桩号</th><th>收敛mm</th><th>状态</th><th>结论</th><th>说明</th></tr>
        </thead>
        <tbody>
          {#each logs as row}
            <tr>
              <td>{row.id}</td>
              <td>{row.chainage}</td>
              <td>{row.delta_mm}</td>
              <td><span class="tag {row.status === 'pending' ? 'pending' : 'ok'}">{row.status === 'pending' ? '待处理' : '已完成'}</span></td>
              <td>
                {#if row.verdict}
                  <span class="tag {row.verdict === '合格' ? 'ok' : 'bad'}">{row.verdict}</span>
                {:else}—{/if}
              </td>
              <td>{row.reason ?? "—"}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}
</main>
