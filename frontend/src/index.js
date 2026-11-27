import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { retireLegacyServiceWorker } from "./legacyWorkerMigration.mjs";
import { recordAppOpen } from "./admin/trafficModel.mjs";

// Retire only the obsolete root caching worker, without reloading this page or
// changing saved sessions, notification settings, or the Firebase worker.
void retireLegacyServiceWorker();

// Count a normal top-level document open once, outside React StrictMode.
void recordAppOpen(window, window.fetch.bind(window), process.env.REACT_APP_BACKEND_URL || '');

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
