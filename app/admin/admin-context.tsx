'use client';

import { createContext, useContext } from 'react';

export interface AdminUser {
  id: string;
  email: string;
  role: string;
  name: string;
}

export const AdminContext = createContext<{ user: AdminUser | null }>({ user: null });
export const useAdminUser = () => useContext(AdminContext);
