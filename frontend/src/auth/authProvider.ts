import type { AuthProvider } from "@refinedev/core";
import { apiClient, setAuthToken } from "../services/apiClient";

type LoginParams = {
  username?: string;
  email?: string;
  password?: string;
};

const TOKEN_KEY = "ai_mid_platform_token";
const USER_KEY = "ai_mid_platform_user";

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
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setAuthToken(null);
    return { success: true, redirectTo: "/login" };
  },
  check: async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
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
      return { logout: true, redirectTo: "/login" };
    }
    return {};
  },
};
