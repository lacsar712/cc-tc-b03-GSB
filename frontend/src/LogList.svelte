<script>
  import { onDestroy, onMount } from "svelte";

  export let session;
  export let authHeaders;
  export let onunauth;

  let logs = [];
  let chainage = "";
  let deltaMm = "";
  let error = "";
  let loading = false;
  let timer;

  $: isWriter = session?.role === "writer";

  async function refresh() {
    const res = await fetch("/api/logs", { headers: authHeaders() });
    if (res.status === 401) {
      onunauth();
      return;
    }
    if (res.ok) logs = await res.json();
  }

  async function submit() {
    error = "";
    loading = true;
    try {
      const res = await fetch("/api/logs", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
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

  onMount(() => {
    refresh();
    timer = setInterval(refresh, 2000);
  });
  onDestroy(() => clearInterval(timer));
</script>

<section class="card">
  <button class="secondary" disabled={loading} on:click={refresh}>刷新列表</button>
</section>
{#if isWriter}
  <section class="card">
    <label>里程桩号</label>
    <input placeholder="例如 K20+050" bind:value={chainage} />
    <label>收敛（毫米，可正可负）</label>
    <input type="number" step="0.1" bind:value={deltaMm} />
    <button disabled={loading} on:click={submit}>提交（进入待认领）</button>
    {#if error}<p class="err">{error}</p>{/if}
  </section>
{/if}
<section class="card">
  <table>
    <thead>
      <tr><th>编号</th><th>桩号</th><th>收敛mm</th><th>状态</th><th>结论</th><th>说明</th></tr>
    </thead>
    <tbody>
      {#each logs as row (row.id)}
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
