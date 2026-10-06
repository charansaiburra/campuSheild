import React, { useState, useEffect } from 'react';
import { Bell, Clock, UserCircle2 } from 'lucide-react';
import { api } from '../services/api';

interface HeaderProps {
  user?: { username: string; role: string };
  unreadAlertsCount?: number;
  onOpenAlert: (alertId: string) => void;
  onUnreadCountChange: (count: number) => void;
}

export const Header: React.FC<HeaderProps> = ({ user, unreadAlertsCount = 0, onOpenAlert, onUnreadCountChange }) => {
  const [time, setTime] = useState<string>('');
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [notificationError, setNotificationError] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<'CHECKING' | 'ONLINE' | 'OFFLINE'>('CHECKING');

  const loadNotifications = async () => {
    setNotificationsLoading(true);
    setNotificationError(null);
    try {
      setNotifications(await api.getNotifications(false));
    } catch (error) {
      setNotificationError(error instanceof Error ? error.message : 'Unable to load notifications');
    } finally {
      setNotificationsLoading(false);
    }
  };

  const openNotification = async (alert: any) => {
    try {
      if (!alert.is_read) await api.markNotificationRead(alert.id);
      setNotifications(current => current.map(item => item.id === alert.id ? { ...item, is_read: true } : item));
      if (!alert.is_read) onUnreadCountChange(Math.max(0, unreadAlertsCount - 1));
      setNotificationsOpen(false);
      onOpenAlert(alert.alert_id || '');
    } catch (error) {
      setNotificationError(error instanceof Error ? error.message : 'Unable to mark notification as read');
    }
  };

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date()));
    }, 1000);
    setTime(new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date()));
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        await api.getHealth();
        if (active) setBackendStatus('ONLINE');
      } catch {
        if (active) setBackendStatus('OFFLINE');
      }
    };
    void check();
    const timer = window.setInterval(() => void check(), 15000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const markAllRead = async () => {
    try {
      await api.markAllNotificationsRead();
      setNotifications(current => current.map(item => ({ ...item, is_read: true })));
      onUnreadCountChange(0);
    } catch (error) {
      setNotificationError(error instanceof Error ? error.message : 'Unable to mark notifications as read');
    }
  };

  return (
    <header className="h-16 bg-slate-900/80 backdrop-blur border-b border-slate-800 px-6 flex items-center justify-between sticky top-0 z-40">
      {/* Status Bar */}
      <div className="flex items-center gap-4">
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold ${backendStatus === 'ONLINE' ? 'bg-emerald-950/60 border border-emerald-800/40 text-emerald-400' : backendStatus === 'OFFLINE' ? 'bg-rose-950/60 border border-rose-800/40 text-rose-300' : 'bg-slate-800 border border-slate-700 text-slate-400'}`}>
          <span className={`w-2 h-2 rounded-full ${backendStatus === 'ONLINE' ? 'bg-emerald-500' : backendStatus === 'OFFLINE' ? 'bg-rose-500' : 'bg-slate-500'}`}></span>
          <span>{backendStatus === 'ONLINE' ? 'API CONNECTED' : backendStatus === 'OFFLINE' ? 'API UNAVAILABLE' : 'CHECKING API'}</span>
        </div>
        <div className="hidden md:flex items-center gap-2 text-slate-400 text-xs font-medium">
          <Clock className="w-3.5 h-3.5 text-slate-500" />
          <span>{time || 'Live Time'}</span>
        </div>
      </div>

      {/* Right User & Actions */}
      <div className="flex items-center gap-4">
        {/* Notifications */}
        <div className="relative">
          <button onClick={() => { const opening = !notificationsOpen; setNotificationsOpen(opening); if (opening) void loadNotifications(); }} aria-label="Notifications" aria-expanded={notificationsOpen} className="p-2 text-slate-400 hover:text-white bg-slate-800/60 rounded-xl border border-slate-700/50 transition relative">
            <Bell className="w-5 h-5" />
            {unreadAlertsCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-rose-500 text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center border-2 border-slate-900">
                {unreadAlertsCount}
              </span>
            )}
          </button>
          {notificationsOpen && (
            <div className="absolute right-0 mt-2 w-80 max-w-[90vw] bg-slate-900 border border-slate-700 rounded-xl shadow-2xl z-50 overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
                <span className="text-xs font-bold text-white">Notifications</span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-slate-500">{unreadAlertsCount} unread</span>
                  {unreadAlertsCount > 0 && <button onClick={() => void markAllRead()} className="text-[10px] text-indigo-300 hover:text-white">Mark all read</button>}
                </div>
              </div>
              {notificationsLoading ? <p className="p-4 text-xs text-slate-400">Loading notifications…</p> :
                notificationError ? <p className="p-4 text-xs text-rose-300">{notificationError}</p> :
                notifications.length === 0 ? <p className="p-4 text-xs text-slate-400">No notifications</p> :
                <div className="max-h-80 overflow-y-auto">
                  {notifications.map(item => (
                    <button key={item.id} onClick={() => void openNotification(item)} className="block w-full text-left px-4 py-3 border-b border-slate-800 hover:bg-slate-800/60">
                      <span className={`block text-xs font-semibold ${item.is_read ? 'text-slate-400' : 'text-white'}`}>{item.title}</span>
                      <span className="block mt-1 text-[11px] text-slate-400 line-clamp-2">{item.description}</span>
                      <span className="block mt-1 text-[10px] text-slate-500">{item.type} · {item.severity} · {item.location || item.camera_name || 'Location unavailable'}</span>
                      <span className="block mt-1 text-[10px] text-slate-500">{new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'short', timeStyle: 'medium' }).format(new Date(item.timestamp))} · {item.is_read ? 'Read' : 'Unread'}</span>
                      {(item.email_delivery || []).map((delivery: any, index: number) => <span key={`${item.id}-email-${index}`} className="block mt-1 text-[10px] text-slate-500">Email: {delivery.status}{delivery.error ? ` · ${delivery.error}` : ''}</span>)}
                    </button>
                  ))}
                </div>
              }
              <button onClick={() => { setNotificationsOpen(false); onOpenAlert(''); }} className="w-full px-4 py-2 text-xs text-indigo-300 hover:bg-slate-800/60">Open Alerts & Incidents</button>
            </div>
          )}
        </div>

        {/* Profile Card */}
        <div className="flex items-center gap-3 pl-3 border-l border-slate-800">
          <div className="w-9 h-9 rounded-full bg-indigo-900/60 border border-indigo-500/40 flex items-center justify-center text-indigo-300">
            <UserCircle2 className="w-6 h-6" />
          </div>
          <div className="hidden sm:block text-left">
            <h4 className="text-xs font-bold text-white leading-tight">{user?.username || 'Security Officer'}</h4>
            <p className="text-[10px] text-slate-400">{user?.role || 'OPERATOR'}</p>
          </div>
        </div>
      </div>
    </header>
  );
};
