import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import "./liquid-glass.css";

const boot = document.getElementById("boot");
if (boot) boot.remove();
// 标题栏由 App 统一渲染：它需要主题 / 玻璃档位 / 侧栏折叠等状态
createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>
);
