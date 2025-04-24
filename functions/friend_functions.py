### IMPORTS ###
from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, send_file
from login_required_wrapper import login_required
import hashlib
from sql_connection import get_connection
import cx_Oracle
import io

from werkzeug.utils import secure_filename
import os

### SQL SETUP ###
oracle_conn = get_connection()

### URL DEFINITIONS ###

@login_required
def search_users():
    """
    Search for users by username
    """
    query = request.args.get('query', '').strip()
    
    if not query:
        return jsonify({'users': []})
    
    try:
        cursor = oracle_conn.cursor()
        # Search for users excluding the current user
        cursor.execute("""
            SELECT user_id, username, first_name, last_name 
            FROM users 
            WHERE LOWER(username) LIKE LOWER(:query) 
            AND user_id != :current_user_id
            AND active = 1
            AND user_id NOT IN (
                SELECT user2_id 
                FROM friends 
                WHERE user1_id = :current_user_id
                UNION
                SELECT user1_id 
                FROM friends 
                WHERE user2_id = :current_user_id
            )
        """, {
            'query': f'%{query}%',
            'current_user_id': session['user_id']
        })
        
        users = [{
            'user_id': row[0],
            'username': row[1],
            'full_name': f"{row[2]} {row[3]}"
        } for row in cursor.fetchall()]
        
        return jsonify({'users': users})
        
    except Exception as e:
        print(f"Error in search_users: {str(e)}")
        return jsonify({'error': 'An error occurred while searching users'}), 500
    finally:
        cursor.close()

@login_required
def add_friend():
    """
    Add a new friend relationship
    """
    try:
        data = request.get_json()
        friend_id = data.get('friend_id')
        
        if not friend_id:
            return jsonify({'success': False, 'message': 'Friend ID is required'}), 400
            
        cursor = oracle_conn.cursor()
        
        # Check if friendship already exists
        cursor.execute("""
            SELECT COUNT(*) FROM friends 
            WHERE (user1_id = :user1_id AND user2_id = :user2_id)
            OR (user1_id = :user2_id AND user2_id = :user1_id)
        """, {
            'user1_id': session['user_id'],
            'user2_id': friend_id
        })
        
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': 'Already friends'}), 400
            
        # Get new friend_id from sequence
        cursor.execute("SELECT friend_id.NEXTVAL FROM DUAL")
        new_friend_id = cursor.fetchone()[0]
        
        # Add friendship
        cursor.execute("""
            INSERT INTO friends (friend_id, user1_id, user2_id, created_at)
            VALUES (:friend_id, :user1_id, :user2_id, CURRENT_TIMESTAMP)
        """, {
            'friend_id': new_friend_id,
            'user1_id': session['user_id'],
            'user2_id': friend_id
        })
        
        oracle_conn.commit()
        return jsonify({'success': True, 'message': 'Friend added successfully'})
        
    except Exception as e:
        oracle_conn.rollback()
        print(f"Error in add_friend: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while adding friend'}), 500
    finally:
        cursor.close()
