from main import app, HOST, PORT

if __name__ == "__main__":
    print(f"Cloud Storage backend running on http://{HOST}:{PORT}")
    app.run(
        host=HOST,
        port=PORT,
        debug=False,
        threaded=True,
    )
