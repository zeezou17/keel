/**
 * Browser entry point. Mounts the React app into the HTML page served by
 * `keel dev` (see keel/static/index.html after running build_frontend.sh).
 */
import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
