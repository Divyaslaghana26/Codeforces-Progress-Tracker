from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd, joblib, os

app = FastAPI(title="Codeforces Rating Predictor API")

MODEL_FILE = "rating_model.joblib"
DATA_FILE = "dataset.csv"

class PredictRequest(BaseModel):
    total_submissions: int
    accepted_submissions: int
    distinct_problems: int
    avg_problem_rating: float = 0.0

@app.get("/status")
def status():
    return {
        "model_exists": os.path.exists(MODEL_FILE),
        "dataset_exists": os.path.exists(DATA_FILE)
    }

@app.get("/dataset")
def get_dataset(sample: int = 10):
    if not os.path.exists(DATA_FILE):
        raise HTTPException(status_code=404, detail="dataset not found – run build_dataset.py")
    df = pd.read_csv(DATA_FILE)
    return df.head(sample).to_dict(orient="records")

@app.post("/predict")
def predict(req: PredictRequest):
    if not os.path.exists(MODEL_FILE):
        raise HTTPException(status_code=404, detail="model not found – run train_model.py first")
    model = joblib.load(MODEL_FILE)
    accept_rate = req.accepted_submissions / req.total_submissions if req.total_submissions > 0 else 0
    X = [[req.total_submissions, req.accepted_submissions, req.distinct_problems, req.avg_problem_rating, accept_rate]]
    pred = model.predict(X)[0]
    return {"predicted_rating": float(pred)}

# To run: uvicorn app:app --reload --port 8000
