<template>
  <main class="page">
    <section class="hero evaluation-home-hero">
      <div class="eyebrow">LLM Agent Evaluation</div>
      <h1>多智能体策略评测与可观测平台</h1>
      <p>面向 LLM Agent 决策质量分析，提供可配置推演场景、Rule / Hybrid 策略评测、共享记忆、决策 Trace 与回放复盘。</p>
      <div class="hero-actions">
        <RouterLink class="primary-btn" to="/evaluation">查看评测仪表盘</RouterLink>
        <RouterLink class="secondary-btn" to="/deployment">配置推演场景</RouterLink>
      </div>
    </section>
    <section class="section-card">
      <div class="section-head">
        <div>
          <div class="eyebrow">Core Loop</div>
          <h2>从 Agent 运行到工程评测闭环</h2>
        </div>
      </div>
      <div class="overview-grid">
        <div class="meta-card">
          <span>策略评测</span>
          <strong>Rule / Hybrid</strong>
          <small>批量运行确定性场景，生成可复现指标。</small>
        </div>
        <div class="meta-card">
          <span>共享记忆</span>
          <strong>Belief</strong>
          <small>融合 observation、risk zone、task 与置信度衰减。</small>
        </div>
        <div class="meta-card">
          <span>LLM Trace</span>
          <strong>Fallback</strong>
          <small>记录 latency、token、解析结果和兜底原因。</small>
        </div>
        <div class="meta-card">
          <span>复盘分析</span>
          <strong>Replay</strong>
          <small>通过帧回放、关键事件和功勋解释定位决策表现。</small>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>
