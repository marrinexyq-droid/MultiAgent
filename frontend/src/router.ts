import { createRouter, createWebHistory } from "vue-router";
import HomePage from "./views/HomePage.vue";
import EvaluationPage from "./views/EvaluationPage.vue";
import HistoryPage from "./views/HistoryPage.vue";
import DeploymentPage from "./views/DeploymentPage.vue";
import BattlePage from "./views/BattlePage.vue";
import ReviewPage from "./views/ReviewPage.vue";

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: HomePage },
    { path: "/evaluation", name: "evaluation", component: EvaluationPage },
    { path: "/history", name: "history", component: HistoryPage },
    { path: "/scenario", redirect: "/deployment" },
    { path: "/deployment", name: "deployment", component: DeploymentPage },
    { path: "/battle/:id", name: "battle", component: BattlePage, props: true },
    { path: "/review/:id", name: "review", component: ReviewPage, props: true },
  ],
});
