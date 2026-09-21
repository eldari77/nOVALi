import React from "react";
import { createRoot } from "react-dom/client";

import { OperatorShellApp } from "./OperatorShellApp";
import "./styles.css";

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <OperatorShellApp />
  </React.StrictMode>,
);
