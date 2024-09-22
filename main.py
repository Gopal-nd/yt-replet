import os
from flask import Flask, render_template, request, send_file, redirect, url_for, after_this_request # type: ignore
import yt_dlp
import logging
import threading
import time
import shutil

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Define download directory
DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')

# Ensure the download directory exists
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Environment port from Render
PORT = int(os.getenv('PORT', 10000))


def clear_download_folder():
    """Clear all files in the download folder."""
    logging.info(f"Attempting to clear download folder: {DOWNLOAD_DIR}")
    try:
        for filename in os.listdir(DOWNLOAD_DIR):
            file_path = os.path.join(DOWNLOAD_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                    logging.info(f"Deleted file: {file_path}")
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    logging.info(f"Deleted directory: {file_path}")
            except Exception as e:
                logging.error(f'Failed to delete {file_path}. Reason: {e}')

        # Verify the folder is empty
        remaining_files = os.listdir(DOWNLOAD_DIR)
        if remaining_files:
            logging.warning(
                f"Files still remaining in download folder: {remaining_files}")
        else:
            logging.info("Download folder successfully cleared.")
    except Exception as e:
        logging.error(
            f"An error occurred while clearing the download folder: {e}")


def periodic_cleanup():
    """Run the cleanup every 10 minutes."""
    while True:
        logging.info("Starting periodic cleanup...")
        clear_download_folder()
        time.sleep(600)  # 600 seconds = 10 minutes


# Start the periodic cleanup in a separate thread
cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
cleanup_thread.start()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/download', methods=['POST'])
def download_video():
    video_url = request.form['url']
    if video_url:
        try:
            # Prepare yt-dlp options for MP4 format
            ydl_opts = {
                'format':
                'mp4',
                'outtmpl':
                f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
            }

            # Download video using yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                video_title = ydl.prepare_filename(info)

            # Correct the file extension
            video_file = os.path.splitext(video_title)[0] + ".mp4"

            logging.info(f"Video downloaded: {video_file}")

            # Ensure the file exists
            if not os.path.exists(video_file):
                logging.error(f"Downloaded file not found: {video_file}")
                return "Error: File not found."

            @after_this_request
            def cleanup(response):
                logging.info("Initiating cleanup after request...")
                clear_download_folder()
                return response

            # Provide the video file for download
            return send_file(video_file, as_attachment=True)

        except Exception as e:
            logging.error(f"An error occurred during download: {str(e)}")
            return f"An error occurred: {str(e)}"

    return redirect(url_for('index'))


if __name__ == '__main__':
    # Bind to the port specified by the environment variable
    app.run(host='0.0.0.0', port=PORT, debug=True)
