<script>
  import { onDestroy, onMount } from "svelte";

  export let session;
  export let authHeaders;
  export let onunauth;

  const BLOCK_W = 130;
  const BLOCK_H = 64;
  const COLORS = { green: "#15803d", red: "#b91c1c", gray: "#57534e" };

  let wall = [];
  let error = "";
  let timer;
  let wallEl;
  let drag = null;
  let editing = false;
  let newChainage = "";
  let newX = "";
  let newY = "";

  $: isWriter = session?.role === "writer";

  async function refresh() {
    if (drag || editing) return; // 拖动或正在改坐标时不覆盖手中数据
    const res = await fetch("/api/wall", { headers: authHeaders() });
    if (res.status === 401) {
      onunauth();
      return;
    }
    if (res.ok) wall = await res.json();
  }

  onMount(() => {
    refresh();
    timer = setInterval(refresh, 2000); // 整面墙定时刷新
  });
  onDestroy(() => clearInterval(timer));

  function colorOf(s) {
    return COLORS[s.color] || COLORS.gray;
  }

  async function addSection() {
    error = "";
    const body = { chainage: newChainage.trim() };
    if (newX !== "") body.x = Number(newX);
    if (newY !== "") body.y = Number(newY);
    const res = await fetch("/api/sections", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      error = data.detail || "添加失败";
      return;
    }
    newChainage = "";
    newX = "";
    newY = "";
    await refresh();
  }

  async function saveSection(s) {
    error = "";
    editing = false;
    const res = await fetch("/api/sections/" + s.id, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ x: Number(s.x), y: Number(s.y) }),
    });
    const data = await res.json();
    if (!res.ok) {
      error = data.detail || "保存失败";
      return;
    }
    await refresh();
  }

  function startDrag(e, s) {
    if (!isWriter || !wallEl) return; // 巡检岗不许改
    const rect = wallEl.getBoundingClientRect();
    drag = { id: s.id, offX: e.clientX - rect.left - s.x, offY: e.clientY - rect.top - s.y };
    window.addEventListener("pointermove", onDragMove);
    window.addEventListener("pointerup", endDrag, { once: true });
    e.preventDefault();
  }

  function onDragMove(e) {
    if (!drag || !wallEl) return;
    const rect = wallEl.getBoundingClientRect();
    const nx = Math.round(Math.max(0, Math.min(rect.width - BLOCK_W, e.clientX - rect.left - drag.offX)));
    const ny = Math.round(Math.max(0, Math.min(rect.height - BLOCK_H, e.clientY - rect.top - drag.offY)));
    wall = wall.map((s) => (s.id === drag.id ? { ...s, x: nx, y: ny } : s));
  }

  async function endDrag() {
    window.removeEventListener("pointermove", onDragMove);
    if (!drag) return;
    const s = wall.find((w) => w.id === drag.id);
    drag = null;
    if (s) await saveSection(s);
  }
</script>

<style>
  .wall-layout { display: flex; gap: 1rem; align-items: flex-start; }
  aside.panel {
    width: 300px; flex: none; background: #292524; border: 1px solid #44403c;
    border-radius: 8px; padding: 1rem 1.25rem;
  }
  aside.panel h3 { margin: 0 0 0.75rem; color: #fbbf24; font-size: 1rem; }
  .xy { display: flex; gap: 0.5rem; }
  .xy > div { flex: 1; }
  ul.sections { list-style: none; margin: 0.75rem 0 0; padding: 0; max-height: 420px; overflow-y: auto; }
  ul.sections li {
    display: flex; align-items: center; gap: 0.4rem; padding: 0.35rem 0;
    border-bottom: 1px solid #44403c; font-size: 0.85rem;
  }
  ul.sections li b { flex: 1; font-weight: 600; }
  .dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
  input.coord { width: 64px; margin-bottom: 0; padding: 0.25rem 0.4rem; font-size: 0.8rem; }
  button.mini { padding: 0.25rem 0.6rem; font-size: 0.8rem; }
  .coordro { color: #a8a29e; font-size: 0.8rem; }
  .hint { color: #a8a29e; font-size: 0.8rem; margin-top: 0.75rem; }
  .wall-wrap { flex: 1; min-width: 0; }
  .legend {
    display: flex; gap: 1rem; align-items: center; font-size: 0.85rem;
    color: #d6d3d1; margin-bottom: 0.5rem;
  }
  .legend i {
    display: inline-block; width: 12px; height: 12px; border-radius: 3px;
    margin-right: 0.3rem; vertical-align: -1px;
  }
  .legend .fresh { margin-left: auto; color: #78716c; font-size: 0.8rem; }
  .wall {
    position: relative; height: 540px; border: 1px solid #44403c; border-radius: 8px;
    background:
      repeating-linear-gradient(0deg, transparent 0 39px, rgba(168, 162, 158, 0.08) 39px 40px),
      repeating-linear-gradient(90deg, transparent 0 39px, rgba(168, 162, 158, 0.08) 39px 40px),
      #0c0a09;
    overflow: hidden;
  }
  .block {
    position: absolute; width: 130px; min-height: 64px; box-sizing: border-box;
    border-radius: 8px; padding: 0.45rem 0.6rem; color: #fff;
    display: flex; flex-direction: column; gap: 0.15rem;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.5); user-select: none; touch-action: none;
  }
  .block.draggable { cursor: grab; }
  .block b { font-size: 0.9rem; }
  .block span { font-size: 0.8rem; opacity: 0.9; }
  .block small { font-size: 0.7rem; opacity: 0.75; }
  .empty { color: #78716c; padding: 1rem; }
</style>

<div class="wall-layout">
  <aside class="panel">
    <h3>坐标维护</h3>
    {#if isWriter}
      <label>桩号</label>
      <input placeholder="例如 K30+000" bind:value={newChainage} />
      <div class="xy">
        <div>
          <label>X（留空自动）</label>
          <input type="number" bind:value={newX} placeholder="自动" />
        </div>
        <div>
          <label>Y（留空自动）</label>
          <input type="number" bind:value={newY} placeholder="自动" />
        </div>
      </div>
      <button on:click={addSection} disabled={!newChainage.trim()}>添加断面</button>
      {#if error}<p class="err">{error}</p>{/if}
    {/if}
    <ul class="sections">
      {#each wall as s (s.id)}
        <li>
          <span class="dot" style="background:{colorOf(s)}"></span>
          <b>{s.chainage}</b>
          {#if isWriter}
            <input
              class="coord"
              type="number"
              bind:value={s.x}
              on:focus={() => (editing = true)}
              on:blur={() => (editing = false)}
            />
            <input
              class="coord"
              type="number"
              bind:value={s.y}
              on:focus={() => (editing = true)}
              on:blur={() => (editing = false)}
            />
            <button class="mini" on:click={() => saveSection(s)}>保存</button>
          {:else}
            <span class="coordro">({Math.round(s.x)}, {Math.round(s.y)})</span>
          {/if}
        </li>
      {/each}
    </ul>
    {#if !isWriter}
      <p class="hint">巡检岗只读：不能改坐标，也不能填报。</p>
    {/if}
  </aside>
  <div class="wall-wrap">
    <div class="legend">
      <span><i style="background:{COLORS.green}"></i>合格</span>
      <span><i style="background:{COLORS.red}"></i>超限</span>
      <span><i style="background:{COLORS.gray}"></i>未办结</span>
      <span class="fresh">整面墙每 2 秒刷新，颜色以接口为准</span>
    </div>
    <div class="wall" bind:this={wallEl}>
      {#each wall as s (s.id)}
        <div
          class="block"
          class:draggable={isWriter}
          style="left:{s.x}px; top:{s.y}px; background:{colorOf(s)}"
          on:pointerdown={(e) => startDrag(e, s)}
        >
          <b>{s.chainage}</b>
          <span>{s.verdict ?? "未办结"}</span>
          <small>{s.last_log_id ? "单据 #" + s.last_log_id : "无办结单据"}</small>
        </div>
      {/each}
      {#if wall.length === 0}
        <p class="empty">还没有断面，请先在左侧维护坐标。</p>
      {/if}
    </div>
  </div>
</div>
