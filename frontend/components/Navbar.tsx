"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function Navbar() {
  const path = usePathname();
  const link = (href: string, label: string) => (
    <Link
      href={href}
      className={`text-sm font-medium transition-colors px-3 py-1.5 rounded-md ${
        path === href
          ? "bg-white/10 text-white"
          : "text-gray-300 hover:text-white hover:bg-white/10"
      }`}
    >
      {label}
    </Link>
  );

  return (
    <nav className="bg-gray-900 border-b border-gray-800 sticky top-0 z-50">
      <div className="container mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-indigo-500 flex items-center justify-center text-sm">
            🤖
          </div>
          <span className="font-semibold text-white tracking-tight">CR Agent</span>
        </div>
        <div className="flex items-center gap-1">
          {link("/", "Findings")}
          {link("/reviews", "Reviews")}
        </div>
      </div>
    </nav>
  );
}
