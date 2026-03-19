'use client';

import { createContext, useContext } from 'react';

export interface AdminUser {
  id: string;
  email: string;
  role: string;
  name: string;
}

export const AdminContext = createContext<{
  user: AdminUser | null;
  questionsBadge: number;
  setQuestionsBadge: (n: number | ((prev: number) => number)) => void;
}>({ user: null, questionsBadge: 0, setQuestionsBadge: () => {} });
export const useAdminUser = () => useContext(AdminContext);
