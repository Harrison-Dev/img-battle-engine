import sqlite3
import json
from datetime import datetime
import os

class Storage:
    def __init__(self, db_path='processing_state.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create processing_jobs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processing_jobs (
                    youtube_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    frame_skip INTEGER NOT NULL,
                    confidence_threshold REAL NOT NULL,
                    current_frame TEXT,
                    total_frames INTEGER,
                    processed_frames INTEGER,
                    last_timestamp REAL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            ''')
            
            # Create frames table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS frames (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    youtube_id TEXT NOT NULL,
                    frame_number TEXT NOT NULL,
                    text TEXT,
                    timestamp REAL,
                    confidence REAL,
                    is_deleted BOOLEAN DEFAULT 0,
                    modified_text TEXT,
                    FOREIGN KEY (youtube_id) REFERENCES processing_jobs(youtube_id),
                    UNIQUE(youtube_id, frame_number)
                )
            ''')
            
            conn.commit()
    
    def extract_youtube_id(self, url):
        """Extract YouTube video ID from URL"""
        if 'youtu.be/' in url:
            return url.split('youtu.be/')[-1].split('?')[0]
        elif 'youtube.com/watch' in url:
            from urllib.parse import parse_qs, urlparse
            return parse_qs(urlparse(url).query)['v'][0]
        return url  # If already an ID
    
    def save_job_state(self, url, status, frame_skip, confidence_threshold, current_progress):
        """Save or update job processing state"""
        youtube_id = self.extract_youtube_id(url)
        now = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if job exists
            cursor.execute('SELECT youtube_id FROM processing_jobs WHERE youtube_id = ?', (youtube_id,))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing job
                cursor.execute('''
                    UPDATE processing_jobs
                    SET status = ?, frame_skip = ?, confidence_threshold = ?,
                        current_frame = ?, total_frames = ?, processed_frames = ?,
                        last_timestamp = ?, updated_at = ?
                    WHERE youtube_id = ?
                ''', (
                    status,
                    frame_skip,
                    confidence_threshold,
                    current_progress.get('frame'),
                    current_progress.get('total_frames', 0),
                    current_progress.get('processed_frames', 0),
                    current_progress.get('timestamp'),
                    now,
                    youtube_id
                ))
            else:
                # Create new job
                cursor.execute('''
                    INSERT INTO processing_jobs
                    (youtube_id, url, status, frame_skip, confidence_threshold,
                     current_frame, total_frames, processed_frames, last_timestamp,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    youtube_id,
                    url,
                    status,
                    frame_skip,
                    confidence_threshold,
                    current_progress.get('frame'),
                    current_progress.get('total_frames', 0),
                    current_progress.get('processed_frames', 0),
                    current_progress.get('timestamp'),
                    now,
                    now
                ))
            
            conn.commit()
    
    def save_frame(self, youtube_id, frame_data):
        """Save frame information"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Convert frame number to timestamp if needed
            frame_number = frame_data['frame']
            timestamp = frame_data.get('timestamp')
            if timestamp is None and frame_number.startswith('frame_'):
                # Extract frame number and convert to timestamp
                try:
                    frame_num = int(frame_number.split('_')[1].split('.')[0])
                    # Assuming 30fps
                    timestamp = frame_num / 30.0
                except:
                    timestamp = 0.0
            
            cursor.execute('''
                INSERT OR REPLACE INTO frames
                (youtube_id, frame_number, text, timestamp, confidence)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                youtube_id,
                frame_data['frame'],
                frame_data.get('text'),
                timestamp,
                frame_data.get('confidence', 0.0)
            ))
            
            conn.commit()
    
    def update_frame(self, youtube_id, frame_number, modified_text=None, is_deleted=None):
        """Update frame information"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            updates = []
            params = []
            
            if modified_text is not None:
                updates.append('modified_text = ?')
                params.append(modified_text)
            
            if is_deleted is not None:
                updates.append('is_deleted = ?')
                params.append(is_deleted)
            
            if updates:
                query = f'''
                    UPDATE frames
                    SET {', '.join(updates)}
                    WHERE youtube_id = ? AND frame_number = ?
                '''
                params.extend([youtube_id, frame_number])
                cursor.execute(query, params)
                conn.commit()
    
    def get_job_state(self, url):
        """Get job state by YouTube URL"""
        youtube_id = self.extract_youtube_id(url)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT *
                FROM processing_jobs
                WHERE youtube_id = ?
            ''', (youtube_id,))
            
            job = cursor.fetchone()
            if not job:
                return None
            
            # Get frames
            cursor.execute('''
                SELECT *
                FROM frames
                WHERE youtube_id = ?
                ORDER BY frame_number
            ''', (youtube_id,))
            
            frames = cursor.fetchall()
            
            return {
                'job': dict(job),
                'frames': [dict(frame) for frame in frames]
            }
    
    def cleanup_job(self, url):
        """Clean up job data but keep the state"""
        youtube_id = self.extract_youtube_id(url)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE processing_jobs
                SET status = 'completed'
                WHERE youtube_id = ?
            ''', (youtube_id,))
            
            conn.commit() 
    
    def get_new_frames(self, youtube_id, last_frame_number=None):
        """Get new frames since the last frame number."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT frame_number, text, modified_text, timestamp, confidence, is_deleted
                    FROM frames
                    WHERE youtube_id = ?
                """
                params = [youtube_id]
                
                if last_frame_number:
                    # Extract frame number from the format 'frame_XXXXXX.jpg'
                    try:
                        last_number = int(last_frame_number.split('_')[1].split('.')[0])
                        query += " AND CAST(SUBSTR(frame_number, 7, 6) AS INTEGER) > ?"
                        params.append(last_number)
                    except (IndexError, ValueError):
                        pass
                
                query += " ORDER BY CAST(SUBSTR(frame_number, 7, 6) AS INTEGER)"
                
                cursor = conn.execute(query, params)
                frames = []
                for row in cursor:
                    frames.append({
                        'frame_number': row[0],
                        'text': row[1],
                        'modified_text': row[2],
                        'timestamp': row[3],
                        'confidence': row[4],
                        'is_deleted': bool(row[5])
                    })
                return frames
        except Exception as e:
            print(f"Error getting new frames: {str(e)}")
            return [] 