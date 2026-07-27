import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./shared/auth/AuthContext.jsx";
import { EmpresaProvider } from "./core/EmpresaContext.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <EmpresaProvider>
          <App />
        </EmpresaProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
