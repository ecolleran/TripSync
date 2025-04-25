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
def create_new_group():
    """
    Redirects to the create group page from dashboard
    This function is called when clicking the 'Create Group' button on dashboard
    """
    return render_template('create_group.html')

@login_required
def create_group():
    """
    Handle group creation functionality
    """
    print("Starting create_group function")  # Debug log
    
    if request.method == 'POST':
        print("Processing POST request")  # Debug log
        
        # Get form data
        group_name = request.form.get('group_name')
        group_description = request.form.get('group_description', '')  # Optional field
        created_by = session['user_id']
        
        print(f"Form data received - Name: {group_name}, Description: {group_description}")  # Debug log
        
        cursor = oracle_conn.cursor()
        try:
            # Get new group_id from sequence
            cursor.execute("SELECT group_id.NEXTVAL FROM DUAL")
            group_id = cursor.fetchone()[0]
            print(f"Generated group_id: {group_id}")  # Debug log
            
            # Handle photo upload
            photo_data = None
            if 'group_photo' in request.files:
                photo = request.files['group_photo']
                if photo and photo.filename != '':
                    photo_data = photo.read()
            
            if not photo_data:
                # Use default photo
                default_photo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images', 'default-group-profile.png')
                with open(default_photo_path, 'rb') as f:
                    photo_data = f.read()

            # Insert into groups table
            cursor.execute("""
                INSERT INTO groups (
                    group_id,
                    group_name,
                    group_description,
                    group_photo,
                    created_by,
                    created_at
                ) VALUES (
                    :1, :2, :3, :4, :5, CURRENT_TIMESTAMP
                )
            """, (group_id, group_name, group_description, photo_data, created_by))
            
            print("Group inserted into database")  # Debug log
            
            # First get the next member_id from a sequence
            cursor.execute("SELECT member_id.NEXTVAL FROM DUAL")
            member_id = cursor.fetchone()[0]

            # Then insert into group_members with the correct structure
            cursor.execute("""
                INSERT INTO group_members (
                    member_id,
                    group_id,
                    user_id,
                    joined_at
                ) VALUES (
                    :1, :2, :3, CURRENT_TIMESTAMP
                )
            """, (member_id, group_id, created_by))
            
            print("Group member entry created")  # Debug log
            
            # Commit the transaction
            oracle_conn.commit()
            print("Transaction committed successfully")  # Debug log
            
            flash('Group created successfully!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            oracle_conn.rollback()
            print(f"Error occurred: {str(e)}")  # Debug log
            flash(f'Error creating group: {str(e)}', 'error')
            return render_template('create_group.html')
            
        finally:
            cursor.close()
            
    # GET request
    return render_template('create_group.html')

@login_required
def group_details(group_id):
    """
    Display group details page
    """
    try:
        cursor = oracle_conn.cursor()
        
        # Get group information
        cursor.execute("""
            SELECT g.group_id, g.group_name, g.group_description, g.group_photo
            FROM groups g
            WHERE g.group_id = :group_id
        """, {'group_id': group_id})
        
        group_data = cursor.fetchone()
        if not group_data:
            flash('Group not found', 'error')
            return redirect(url_for('dashboard'))
        
        # Convert group photo to base64 if it exists
        group_photo_b64 = None
        if group_data[3]:  # if group_photo exists
            import base64
            # Read the LOB object
            photo_data = group_data[3].read()
            group_photo_b64 = base64.b64encode(photo_data).decode('utf-8')
            
        group = {
            'id': group_data[0],
            'name': group_data[1],
            'description': group_data[2],
            'photo': group_photo_b64
        }
        
        # Get group trips with formatted dates from Oracle
        cursor.execute("""
            SELECT t.trip_id, 
                   t.trip_name, 
                   TO_CHAR(t.start_date, 'Month DD, YYYY') as start_date, 
                   TO_CHAR(t.end_date, 'Month DD, YYYY') as end_date
            FROM trips t
            WHERE t.group_id = :group_id
            ORDER BY t.start_date DESC
        """, {'group_id': group_id})
        
        trips = [{
            'trip_id': row[0],
            'name': row[1],
            'start_date': row[2],
            'end_date': row[3],
            'image_url': url_for('static', filename='images/default-trip.png')
        } for row in cursor.fetchall()]
        
        # Get group members with their profile pictures
        cursor.execute("""
            SELECT u.user_id, u.first_name, u.last_name, u.profile_picture
            FROM users u
            JOIN group_members gm ON u.user_id = gm.user_id
            WHERE gm.group_id = :group_id
        """, {'group_id': group_id})
        
        members = []
        for row in cursor.fetchall():
            profile_picture_b64 = None
            if row[3]:  # if profile_picture exists
                import base64
                # Read the LOB object
                photo_data = row[3].read()
                profile_picture_b64 = base64.b64encode(photo_data).decode('utf-8')
                
            members.append({
                'id': row[0],
                'name': f"{row[1]} {row[2]}",
                'profile_picture': profile_picture_b64,
                'role': 'Member'
            })
        
        return render_template('group_details.html', 
                             group=group,
                             trips=trips,
                             members=members)
                             
    except Exception as e:
        print(f"Error in group_details: {str(e)}")  # Add this for debugging
        flash(f'Error loading group details: {str(e)}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()

@login_required
def search_users_for_group():
    """
    Search for users to add to a group
    """
    query = request.args.get('query', '')
    group_id = request.args.get('group_id')
    
    if not query or not group_id:
        return jsonify({'users': []})
    
    cursor = oracle_conn.cursor()
    try:
        # Search for users that match the query and are not already in the group
        cursor.execute("""
            SELECT u.user_id, u.username, u.first_name || ' ' || u.last_name as full_name
            FROM users u
            WHERE (LOWER(u.username) LIKE LOWER(:query) 
                  OR LOWER(u.first_name || ' ' || u.last_name) LIKE LOWER(:query))
            AND u.user_id NOT IN (
                SELECT user_id 
                FROM group_members 
                WHERE group_id = :group_id
            )
            AND u.user_id != :current_user_id
            AND ROWNUM <= 5
        """, {
            'query': f'%{query}%',
            'group_id': group_id,
            'current_user_id': session['user_id']
        })
        
        users = [{
            'user_id': row[0],
            'username': row[1],
            'full_name': row[2]
        } for row in cursor.fetchall()]
        
        return jsonify({'users': users})
        
    except Exception as e:
        print(f"Error searching users: {str(e)}")
        return jsonify({'error': 'An error occurred while searching users'}), 500
    finally:
        cursor.close()

@login_required
def add_group_member():
    """
    Add a new member to a group
    """
    data = request.get_json()
    user_id = data.get('user_id')
    group_id = data.get('group_id')
    
    if not user_id or not group_id:
        return jsonify({'success': False, 'message': 'Missing required data'})
    
    cursor = oracle_conn.cursor()
    try:
        # Check if user is already a member
        cursor.execute("""
            SELECT 1 FROM group_members 
            WHERE group_id = :group_id AND user_id = :user_id
        """, {'group_id': group_id, 'user_id': user_id})
        
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'User is already a member of this group'})
        
        # Get next member_id
        cursor.execute("SELECT NVL(MAX(member_id), 0) + 1 FROM group_members")
        member_id = cursor.fetchone()[0]
        
        # Add user to group
        cursor.execute("""
            INSERT INTO group_members (member_id, group_id, user_id, joined_at)
            VALUES (:member_id, :group_id, :user_id, CURRENT_TIMESTAMP)
        """, {
            'member_id': member_id,
            'group_id': group_id,
            'user_id': user_id
        })
        
        oracle_conn.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        oracle_conn.rollback()
        print(f"Error adding group member: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while adding member'})
    finally:
        cursor.close()

@login_required
def edit_group_page(group_id):
    """
    Display the edit group page
    """
    try:
        cursor = oracle_conn.cursor()
        
        # Get group information
        cursor.execute("""
            SELECT g.group_id, g.group_name, g.group_description, g.group_photo, g.created_by
            FROM groups g
            WHERE g.group_id = :group_id
        """, {'group_id': group_id})
        
        group_data = cursor.fetchone()
        if not group_data:
            flash('Group not found', 'error')
            return redirect(url_for('dashboard'))
            
        # Convert group photo to base64 if it exists
        group_photo_b64 = None
        if group_data[3]:
            import base64
            photo_data = group_data[3].read()
            group_photo_b64 = base64.b64encode(photo_data).decode('utf-8')
            
        group = {
            'id': group_data[0],
            'name': group_data[1],
            'description': group_data[2],
            'photo': group_photo_b64
        }
        
        # Get group members
        cursor.execute("""
            SELECT u.user_id, u.first_name, u.last_name, u.profile_picture
            FROM users u
            JOIN group_members gm ON u.user_id = gm.user_id
            WHERE gm.group_id = :group_id
        """, {'group_id': group_id})
        
        members = []
        for row in cursor.fetchall():
            profile_picture_b64 = None
            if row[3]:
                import base64
                photo_data = row[3].read()
                profile_picture_b64 = base64.b64encode(photo_data).decode('utf-8')
                
            members.append({
                'id': row[0],
                'name': f"{row[1]} {row[2]}",
                'profile_picture': profile_picture_b64
            })
        
        return render_template('edit_group.html', 
                             group=group,
                             members=members)
                             
    except Exception as e:
        print(f"Error in edit_group_page: {str(e)}")
        flash(f'Error loading group details: {str(e)}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()

@login_required
def edit_group(group_id):
    """
    Handle group editing functionality
    """
    if request.method == 'POST':
        cursor = oracle_conn.cursor()
        try:
            # Check if user is the group creator
            cursor.execute("""
                SELECT created_by FROM groups 
                WHERE group_id = :group_id
            """, {'group_id': group_id})
            
            # Get form data
            group_name = request.form.get('group_name')
            group_description = request.form.get('group_description', '')
            
            # Handle photo upload
            photo_data = None
            if 'group_photo' in request.files:
                photo = request.files['group_photo']
                if photo and photo.filename != '':
                    photo_data = photo.read()
            
            # Update group information
            if photo_data:
                cursor.execute("""
                    UPDATE groups 
                    SET group_name = :name,
                        group_description = :description,
                        group_photo = :photo
                    WHERE group_id = :group_id
                """, {
                    'name': group_name,
                    'description': group_description,
                    'photo': photo_data,
                    'group_id': group_id
                })
            else:
                cursor.execute("""
                    UPDATE groups 
                    SET group_name = :name,
                        group_description = :description
                    WHERE group_id = :group_id
                """, {
                    'name': group_name,
                    'description': group_description,
                    'group_id': group_id
                })
            
            oracle_conn.commit()
            flash('Group updated successfully!', 'success')
            return redirect(url_for('group_details', group_id=group_id))
            
        except Exception as e:
            oracle_conn.rollback()
            flash(f'Error updating group: {str(e)}', 'error')
            return redirect(url_for('edit_group_page', group_id=group_id))
        finally:
            cursor.close()
            
    return redirect(url_for('edit_group_page', group_id=group_id))

@login_required
def remove_group_member():
    """
    Remove a member from a group
    """
    data = request.get_json()
    user_id = data.get('user_id')
    group_id = data.get('group_id')
    
    if not user_id or not group_id:
        return jsonify({'success': False, 'message': 'Missing required data'})
    
    cursor = oracle_conn.cursor()
    try:
        # Remove the member
        cursor.execute("""
            DELETE FROM group_members 
            WHERE group_id = :group_id AND user_id = :user_id
        """, {
            'group_id': group_id,
            'user_id': user_id
        })
        
        oracle_conn.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        oracle_conn.rollback()
        print(f"Error removing group member: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while removing member'})
    finally:
        cursor.close()

@login_required
def delete_group(group_id):
    """
    Delete a group
    """
    cursor = oracle_conn.cursor()
    try:
        # Check if user is the group creator
        cursor.execute("""
            SELECT created_by FROM groups 
            WHERE group_id = :group_id
        """, {'group_id': group_id})
        
        creator = cursor.fetchone()
        if not creator or creator[0] != session['user_id']:
            flash('You do not have permission to delete this group', 'error')
            return redirect(url_for('group_details', group_id=group_id))
        
        # Delete all group members
        cursor.execute("""
            DELETE FROM group_members 
            WHERE group_id = :group_id
        """, {'group_id': group_id})
        
        # Delete all group trips
        cursor.execute("""
            DELETE FROM trips 
            WHERE group_id = :group_id
        """, {'group_id': group_id})
        
        # Delete the group
        cursor.execute("""
            DELETE FROM groups 
            WHERE group_id = :group_id
        """, {'group_id': group_id})
        
        oracle_conn.commit()
        flash('Group deleted successfully!', 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        oracle_conn.rollback()
        flash(f'Error deleting group: {str(e)}', 'error')
        return redirect(url_for('group_details', group_id=group_id))
    finally:
        cursor.close()



