import ReactDOM from "react-dom/client";
import { App } from "./App";
import { Admin } from "./Admin";
import "./styles.css";
import "./journey.css";
ReactDOM.createRoot(document.getElementById("root")!).render(
  location.pathname === "/admin" ? <Admin /> : <App />,
);
