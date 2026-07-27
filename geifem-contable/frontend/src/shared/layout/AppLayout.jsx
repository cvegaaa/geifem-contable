import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar/index.jsx";
import Topbar from "./Topbar/index.jsx";

export default function AppLayout() {
  return (
    <div className="min-h-screen flex bg-slate-50">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar />
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
