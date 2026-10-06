import React, { useState, useEffect, useCallback } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { Login } from './pages/Login';
import { DashboardPage } from './pages/DashboardPage';
import { LiveMonitoringPage } from './pages/LiveMonitoringPage';
import { CamerasPage } from './pages/CamerasPage';
import { MembersPage } from './pages/MembersPage';
import { PersonIdentificationPage } from './pages/PersonIdentificationPage';
import { ZonesPage } from './pages/ZonesPage';
import { EventsPage } from './pages/EventsPage';
import { AlertsPage } from './pages/AlertsPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { ReportsPage } from './pages/ReportsPage';
import { SettingsPage } from './pages/SettingsPage';
import { api } from './services/api';

export function App() {
  const [user, setUser] = useState<any>(null);
  const [currentTab, setCurrentTab] = useState('dashboard');
  const [loading, setLoading] = useState(true);
  const [unreadAlertsCount, setUnreadAlertsCount] = useState(0);
  const [focusAlertId, setFocusAlertId] = useState<string | null>(null);

  useEffect(() => {
    checkAuth();
  }, []);

  const refreshUnreadAlerts = useCallback(async () => {
    if (!user) { setUnreadAlertsCount(0); return; }
    try {
      const result = await api.getUnreadNotificationCount();
      setUnreadAlertsCount(result.count);
    } catch (e) {
      console.error('Failed to refresh unread security alerts:', e);
    }
  }, [user]);

  useEffect(() => {
    void refreshUnreadAlerts();
    if (!user) return;
    const timer = window.setInterval(() => void refreshUnreadAlerts(), 15000);
    return () => window.clearInterval(timer);
  }, [refreshUnreadAlerts, user]);

  const checkAuth = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const u = await api.getMe();
      setUser(u);
    } catch (e) {
      localStorage.removeItem('access_token');
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    setUser(null);
  };

  const openNotification = (alertId: string) => {
    setFocusAlertId(alertId);
    setCurrentTab('alerts');
    void refreshUnreadAlerts();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400 text-sm">
        Initializing CampusShield Web Platform...
      </div>
    );
  }

  if (!user) {
    return <Login onLoginSuccess={(u) => setUser(u)} />;
  }

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      {/* Navigation Sidebar */}
      <Sidebar
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        userRole={user.role}
        onLogout={handleLogout}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header user={user} unreadAlertsCount={unreadAlertsCount} onOpenAlert={openNotification} onUnreadCountChange={setUnreadAlertsCount} />

        <main className="flex-1 overflow-y-auto">
          {currentTab === 'dashboard' && <DashboardPage onNavigate={setCurrentTab} />}
          {currentTab === 'live-monitoring' && <LiveMonitoringPage />}
          {currentTab === 'cameras' && <CamerasPage />}
          {currentTab === 'members' && <MembersPage />}
          {currentTab === 'person-identification' && <PersonIdentificationPage onNavigate={setCurrentTab} />}
          {currentTab === 'zones' && <ZonesPage />}
          {currentTab === 'events' && <EventsPage />}
          {currentTab === 'alerts' && <AlertsPage focusAlertId={focusAlertId} />}
          {currentTab === 'analytics' && <AnalyticsPage />}
          {currentTab === 'reports' && <ReportsPage />}
          {currentTab === 'settings' && user.role === 'ADMIN' && <SettingsPage />}
        </main>
      </div>
    </div>
  );
}

export default App;
