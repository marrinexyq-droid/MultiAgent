<template>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">Confrontation Platform</div>
      <h1>多智能体对抗演练平台</h1>
      <p>Vue 版本作为正式前端入口，承接大厅、部署、战场与结算。</p>
      <div class="hero-actions">
        <RouterLink class="primary-btn" to="/deployment">开始部署</RouterLink>
        <RouterLink class="secondary-btn" to="/hex-lab">进入六边形试验场</RouterLink>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>
