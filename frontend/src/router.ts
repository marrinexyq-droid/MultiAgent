import { createRouter, createWebHistory } from "vue-router";
import HomePage from "./views/HomePage.vue";
import EvaluationPage from "./views/EvaluationPage.vue";
import DeploymentPage from "./views/DeploymentPage.vue";
import BattlePage from "./views/BattlePage.vue";
import ReviewPage from "./views/ReviewPage.vue";
import HexLabPage from "./views/HexLabPage.vue";
import FantasyPage from "./views/FantasyPage.vue";

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: HomePage },
    { path: "/evaluation", name: "evaluation", component: EvaluationPage },
    { path: "/scenario", redirect: "/deployment" },
    { path: "/deployment", name: "deployment", component: DeploymentPage },
    { path: "/hex-lab", name: "hex-lab", component: HexLabPage },
    { path: "/fantasy", name: "fantasy", component: FantasyPage },
    { path: "/battle/:id", name: "battle", component: BattlePage, props: true },
    { path: "/review/:id", name: "review", component: ReviewPage, props: true },
  ],
});
