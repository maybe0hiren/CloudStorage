from main import app


if __name__ == "__main__":
    from main import HOST, PORT

    print(f"Overcast backend running on http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
