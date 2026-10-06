export interface User {
  id: string;
  username: string;
  email: string;
  role: 'ADMIN' | 'SECURITY_OFFICER';
  is_active: boolean;
}

export interface CollegeMember {
  id: string;
  name: string;
  college_id: string;
  role: 'STUDENT' | 'FACULTY' | 'TEACHING_STAFF' | 'NON_TEACHING_STAFF' | 'SECURITY_STAFF' | 'AUTHORIZED_VISITOR';
  department?: string;
  year?: string;
  email?: string;
  status: 'ACTIVE' | 'INACTIVE';
  face_enrolled: boolean;
  sample_count?: number;
  created_at?: string;
}

export interface Camera {
  id: string;
  name: string;
  location: string;
  source_type: 'WEBCAM' | 'VIDEO_FILE' | 'RTSP';
  source_url?: string;
  status: 'ONLINE' | 'OFFLINE' | 'ERROR';
  last_seen?: string;
}

export interface RestrictedZone {
  id: string;
  camera_id: string;
  name: string;
  zone_type: string;
  polygon: number[][];
  allowed_roles: string[];
  occupancy_threshold: number;
  is_active: boolean;
}

export interface SecurityEvent {
  id: string;
  camera_id?: string;
  zone_id?: string;
  track_id?: number;
  member_id?: string;
  member_name?: string;
  event_type: string;
  severity: 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  location?: string;
  description?: string;
  snapshot_path?: string;
  status: 'NEW' | 'ACKNOWLEDGED' | 'RESOLVED' | 'DISMISSED';
  timestamp?: string;
  created_at?: string;
  acknowledged_at?: string;
  resolved_at?: string;
}

export interface Alert {
  id: string;
  event_id?: string;
  camera_id?: string;
  severity: 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  title: string;
  description?: string;
  status: 'NEW' | 'ACKNOWLEDGED' | 'RESOLVED' | 'DISMISSED';
  timestamp?: string;
  event_type?: string;
  track_id?: number;
  member_id?: string;
  member_name?: string;
  location?: string;
  camera_name?: string;
  snapshot_path?: string;
}
