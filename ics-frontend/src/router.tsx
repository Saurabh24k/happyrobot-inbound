// src/router.tsx
import { createBrowserRouter } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Calls from './pages/Calls';
import CallDetail from './pages/CallDetail';
import Loads from './pages/Loads';
import Settings from './pages/Settings';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'calls', element: <Calls /> },
      { path: 'calls/:id', element: <CallDetail /> },
      { path: 'loads', element: <Loads /> },
      { path: 'settings', element: <Settings /> },
    ],
  },
]);

export default router;
