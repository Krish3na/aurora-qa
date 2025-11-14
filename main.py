import uvicorn

# launch the API locally
if __name__ == "__main__":
    # print("launching API server on http://localhost:8000 ...")
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=True)


