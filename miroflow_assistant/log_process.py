import json
import os
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.file_utils import save_json

# Configuration Variables
# Normal Mode
MAIN_AGENT_USER_PRE_LEN = 5000
MAIN_AGENT_USER_POST_LEN = 1000
SUB_AGENT_USER_PRE_LEN = 2000
SUB_AGENT_USER_POST_LEN = 500
SUB_AGENT_ASSISTANT_PRE_LEN = 4000
SUB_AGENT_ASSISTANT_POST_LEN = 1000

# Aggressive Mode (for huge logs > 1MB)
AGG_MAIN_AGENT_USER_PRE_LEN = 3000
AGG_MAIN_AGENT_USER_POST_LEN = 500
AGG_SUB_AGENT_USER_PRE_LEN = 1000
AGG_SUB_AGENT_USER_POST_LEN = 500
AGG_SUB_AGENT_ASSISTANT_PRE_LEN = 2000
AGG_SUB_AGENT_ASSISTANT_POST_LEN = 500

TRUNCATION_PLACEHOLDER = "..."
HUGE_LOG_THRESHOLD = 1000000

def _truncate_content(content, role, mode='main', config=None):
    if not isinstance(content, str):
        return content
        
    length = len(content)
    
    # Select configuration based on mode
    if config:
        # Use provided dynamic config
        if mode == 'main':
            if role == 'user':
                pre_len = config['MAIN_USER_PRE']
                post_len = config['MAIN_USER_POST']
            else: # assistant
                return content
        elif mode == 'sub':
            if role == 'user':
                pre_len = config['SUB_USER_PRE']
                post_len = config['SUB_USER_POST']
            elif role == 'assistant':
                pre_len = config['SUB_ASSISTANT_PRE']
                post_len = config['SUB_ASSISTANT_POST']
            else:
                return content
        else:
            return content
    else:
        # Fallback to global constants (Normal Mode logic)
        if mode == 'main':
            if role == 'user':
                pre_len = MAIN_AGENT_USER_PRE_LEN
                post_len = MAIN_AGENT_USER_POST_LEN
            else: # assistant
                return content
        elif mode == 'sub':
            if role == 'user':
                pre_len = SUB_AGENT_USER_PRE_LEN
                post_len = SUB_AGENT_USER_POST_LEN
            elif role == 'assistant':
                pre_len = SUB_AGENT_ASSISTANT_PRE_LEN
                post_len = SUB_AGENT_ASSISTANT_POST_LEN
            else:
                return content
        else:
            return content

    if length <= pre_len + post_len:
        return content
    
    return content[:pre_len] + TRUNCATION_PLACEHOLDER + content[-post_len:]

def get_message_content_length(data):
    """Calculates total length of content in message history."""
    total_len = 0
    
    # Main agent history
    main_msgs = data.get('main_agent_message_history', {}).get('message_history', [])
    if main_msgs:
        for msg in main_msgs:
            content = msg.get('content')
            if isinstance(content, str):
                total_len += len(content)
                
    # Sub agent sessions
    sub_sessions = data.get('sub_agent_message_history_sessions', {})
    if sub_sessions:
        for session in sub_sessions.values():
            sub_msgs = session.get('message_history', [])
            if sub_msgs:
                for msg in sub_msgs:
                    content = msg.get('content')
                    if isinstance(content, str):
                        total_len += len(content)
                        
    return total_len

def process_log_data(file_path):
    """
    Reads a JSON log file, cleans the data by extracting metadata and truncating message content,
    and returns the cleaned data dictionary.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON file: {file_path}")

    # Check size and determine compression mode
    total_content_len = get_message_content_length(data)
    use_aggressive = total_content_len > HUGE_LOG_THRESHOLD
    
    truncation_config = None
    if use_aggressive:
        print(f"Log {file_path} content size {total_content_len} exceeds limit {HUGE_LOG_THRESHOLD}. Using aggressive compression.")
        truncation_config = {
            'MAIN_USER_PRE': AGG_MAIN_AGENT_USER_PRE_LEN,
            'MAIN_USER_POST': AGG_MAIN_AGENT_USER_POST_LEN,
            'SUB_USER_PRE': AGG_SUB_AGENT_USER_PRE_LEN,
            'SUB_USER_POST': AGG_SUB_AGENT_USER_POST_LEN,
            'SUB_ASSISTANT_PRE': AGG_SUB_AGENT_ASSISTANT_PRE_LEN,
            'SUB_ASSISTANT_POST': AGG_SUB_AGENT_ASSISTANT_POST_LEN
        }
    else:
        # Explicit normal config to keep logic consistent, or None to fall back to globals
        # Let's pass the normal config to be explicit and avoid the complex fallback logic inside _truncate_content if we wanted
        # But to minimize changes to _truncate_content structure I already wrote above, I'll pass None for normal to use global constants
        pass 

    cleaned_data = {}

    # Extract metadata
    cleaned_data['status'] = data.get('status')
    cleaned_data['start_time'] = data.get('start_time')
    cleaned_data['task_id'] = data.get('task_id')
    
    # helper for nested dict access safety
    input_data = data.get('input', {})
    cleaned_data['task_description'] = input_data.get('task_description')

    # Process main_agent_message_history
    main_history = data.get('main_agent_message_history', {})
    cleaned_main_history = {}
    
    # Keep system prompt
    if 'system_prompt' in main_history:
        cleaned_main_history['system_prompt'] = main_history['system_prompt']
        
    # Process messages
    raw_messages = main_history.get('message_history', [])
    cleaned_messages = []
    if raw_messages:
        for msg in raw_messages:
            role = msg.get('role')
            content = msg.get('content')
            
            new_msg = msg.copy()
            new_msg['content'] = _truncate_content(content, role, mode='main', config=truncation_config)
            cleaned_messages.append(new_msg)
            
    if raw_messages:
        cleaned_main_history['message_history'] = cleaned_messages
    elif 'message_history' in main_history: # preserve empty list if it existed
        cleaned_main_history['message_history'] = []

    if main_history:
        cleaned_data['main_agent_message_history'] = cleaned_main_history
    

    # Process sub_agent_message_history_sessions
    sub_sessions = data.get('sub_agent_message_history_sessions', {})
    cleaned_sub_sessions = {}
    
    if sub_sessions:
        for agent_name, session_data in sub_sessions.items():
            cleaned_session = {}
            # Discard system prompt (implied by requirement "retain system prompt" only for main agent, 
            # and requirement "discard system prompt" for sub agents)
            
            # Process messages
            raw_sub_messages = session_data.get('message_history', [])
            cleaned_sub_messages = []
            
            if raw_sub_messages:
                for msg in raw_sub_messages:
                    role = msg.get('role')
                    content = msg.get('content')
                    
                    new_msg = msg.copy()
                    new_msg['content'] = _truncate_content(content, role, mode='sub', config=truncation_config)
                    cleaned_sub_messages.append(new_msg)
            
            if raw_sub_messages:
                 cleaned_session['message_history'] = cleaned_sub_messages
            elif 'message_history' in session_data:
                 cleaned_session['message_history'] = []

            cleaned_sub_sessions[agent_name] = cleaned_session
            
    if sub_sessions:
        cleaned_data['sub_agent_message_history_sessions'] = cleaned_sub_sessions
    else:
        cleaned_data['sub_agent_message_history_sessions'] = {}

    # step_logs and trace_data are implicitly dropped by not adding them to cleaned_data

    return cleaned_data


if __name__ == "__main__":
    processed_log = process_log_data("test/long_text_C3FBBFA9-1F78-40CE-A535-E3B662A5DC24.json")
    save_json(processed_log, "processed_log3.json")