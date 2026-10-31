import StudioMotion from "./components/StudioMotion";
import React from "react";
import ReactDOM from "react-dom/client";
import RecoveryScene from "./components/RecoveryScene";
import App from "./App";
import "./style.css";
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <StudioMotion />
    <RecoveryScene>
      <App />
    </RecoveryScene>
  </React.StrictMode>,
);
