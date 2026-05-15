import type { AuthProvider } from "@refinedev/core";
import { apiClient, clearAuthStorage, setAuthToken, TOKEN_KEY, USER_KEY } from "../services/apiClient";

type LoginParams = {
  username?: string;
  email?: string;
  password?: string;
};

const isJwtExpired = (token: string) => {
  try {
    const [, payload] = token.split(".");
    if (!payload) {
      return true;
    }
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const decoded = JSON.parse(window.atob(padded)) as { exp?: number };
    if (!decoded.exp) {
      return false;
    }
    return decoded.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
};

export const authProvider: AuthProvider = {
  login: async ({ username, email, password }: LoginParams) => {
    const form = new URLSearchParams();
    form.append("username", username ?? email ?? "");
    form.append("password", password ?? "");

    const { data } = await apiClient.post("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });

    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    setAuthToken(data.access_token);

    return { success: true, redirectTo: "/" };
  },
  logout: async () => {
    clearAuthStorage();
    return { success: true, redirectTo: "/login" };
  },
  check: async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token || isJwtExpired(token)) {
      clearAuthStorage();
      return { authenticated: false, redirectTo: "/login" };
    }
    setAuthToken(token);
    return { authenticated: true };
  },
  getIdentity: async () => {
    const user = localStorage.getItem(USER_KEY);
    return user ? JSON.parse(user) : null;
  },
  getPermissions: async () => {
    const user = localStorage.getItem(USER_KEY);
    return user ? JSON.parse(user).permissions : [];
  },
  onError: async (error) => {
    if (error?.response?.status === 401) {
      clearAuthStorage();
      return { logout: true, redirectTo: "/login" };
    }
    return {};
  },
};
