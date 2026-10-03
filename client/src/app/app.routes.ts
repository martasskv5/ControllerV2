import { Routes } from "@angular/router";

export const routes: Routes = [
    {
        path: "",
        loadComponent: () => import("./mediapage/mediapage").then((module) => module.Mediapage),
    },
    {
        path: "settings",
        loadComponent: () => import("./settingspage/settingspage").then((module) => module.SettingsPage),
    },
    {
        path: "**",
        redirectTo: "",
    },
];