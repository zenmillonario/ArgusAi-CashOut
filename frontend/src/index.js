import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { retireLegacyServiceWorker } from "./legacyWorkerMigration.mjs";

// Retire only the obsolete root caching worker, without reloading this page or
// changing saved sessions, notification settings, or the Firebase worker.
void retireLegacyServiceWorker();

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
