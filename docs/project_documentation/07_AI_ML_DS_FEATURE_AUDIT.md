# 07 — AI, Machine Learning & Data Science Feature Audit

This audit provides an academic and code-grounded evaluation of all Artificial Intelligence (AI), Machine Learning (ML), Statistical, and Heuristic algorithms implemented in the project.

---

## 1. Classification of AI / ML / DS Components

```
+----------------------------------------------------------------------------------------------------+
|                                    PROJECT INTELLIGENCE TAXONOMY                                   |
+------------------------------------+----------------------------------+----------------------------+
| 1. SUPERVISED MACHINE LEARNING     | 2. MULTI-ATTRIBUTE HEURISTICS    | 3. DATA SCIENCE ANALYTICS  |
| - Linear Regression (Scikit-Learn) | - Smart Printer Selection        | - Busy-Hour Clustering     |
| - 7-Day Revenue & Volume Forecast  | - Queue Balancing Scoring Engine | - Anomaly Detection        |
| - Print Completion Duration Model  | - Capability Constraint Matcher  | - Daily Aggregation Models |
+------------------------------------+----------------------------------+----------------------------+
| 4. NATURAL LANGUAGE INTERACTION    | 5. COMPUTER VISION & PREVIEW     | 6. RULE-BASED AUTOMATION   |
| - Web Speech API Voice Controller  | - PDF Rasterization (pdf2image)  | - Tiered Pricing Engine    |
| - Regex Intent & Entity Extractor  | - Binary Magic Byte Inspection   | - Payment-Gated State Flow |
+------------------------------------+----------------------------------+----------------------------+
```

---

## 2. Supervised Machine Learning Implementation

### 2.1 Revenue & Print Volume Forecasting Model
- **File & Function**: `cloud_server/app/services/analytics_service.py` -> `forecast_revenue_ml()` ([L280-L360](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/services/analytics_service.py#L280-L360))
- **Algorithm**: **Ordinary Least Squares (OLS) Linear Regression** via `sklearn.linear_model.LinearRegression`.
- **Mathematical Formulation**:
  $$\hat{y}_t = \beta_0 + \beta_1 \cdot t + \epsilon$$
  where $t$ represents time indices over historical days, and $\hat{y}_t$ represents projected daily revenue ($\text{INR}$) and total page volume.
- **Input Features**:
  1. $X$: Sequential time indices ($t \in [1, N]$) from `AnalyticsDaily` records.
  2. Rolling window features (past 7 to 30 days).
- **Target Output**: Projected revenue and total pages for $t+1$ through $t+7$ days.
- **Fallback Mechanism**: When historical data points are fewer than `ML_MIN_TRAINING_RECORDS` ($N < 3$), falls back to weighted exponential moving averages (EMA).
- **Evaluation**: Computes $R^2$ coefficient of determination to measure model fit confidence.

---

### 2.2 Print Completion Time Prediction Model
- **File & Function**: `cloud_server/app/services/ml_prediction_service.py` -> `predict_job_completion_time()` ([L60-L140](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/services/ml_prediction_service.py#L60-L140))
- **Algorithm**: **Multi-variable Linear Regression** (`scikit-learn`).
- **Feature Vector**:
  $$\mathbf{x} = [\text{total\_pages}, \text{copies}, \text{is\_color}, \text{is\_duplex}, \text{current\_queue\_length}]$$
- **Target**: Duration in seconds until physical job completion.
- **Training Source**: Trained on completed `ActiveJob` rows where $\text{duration} = \text{completed\_at} - \text{started\_at}$.

---

## 3. Intelligent Multi-Attribute Heuristics

### 3.1 Smart Printer Selection Algorithm (Candidate Scoring)
- **File & Function**: `cloud_server/app/services/assignment_service.py` -> `select_best_printer()` ([L30-L120](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/services/assignment_service.py#L30-L120))
- **Decision Workflow**:
  1. **Hard Constraint Filtering**: Eliminates printers that are `OFFLINE`, in `ERROR`, or lack required capabilities (e.g. eliminating B&W-only printers for a color job, or single-feed printers for duplex jobs).
  2. **Soft Scoring Optimization**:
     $$\text{Score}(P) = w_1 \cdot \text{QueueDepth}(P) + w_2 \cdot \text{SpeedRating}(P) + w_3 \cdot \text{WorkloadBalance}(P)$$
     - Printer with lowest weighted score is automatically assigned the incoming job.

---

## 4. Data Science & Business Intelligence Analytics

### 4.1 Shop Peak-Hour Clustering & Traffic Analysis
- **File & Function**: `cloud_server/app/services/analytics_service.py` -> `detect_busy_hours()` ([L390-L450](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/services/analytics_service.py#L390-L450))
- **Technique**: Frequency distribution histogram over 24 hourly bins ($\text{hour} \in [0, 23]$), identifying peak operational density using z-score thresholding ($\mu + 1.5\sigma$).

### 4.2 Automated Anomaly Detection
- **File & Function**: `cloud_server/app/services/analytics_service.py` -> `detect_daily_anomalies()` ([L480-L540](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/services/analytics_service.py#L480-L540))
- **Technique**: Compares daily print error rates and abnormal payment failures against the 30-day baseline standard deviation. Flags `anomaly_detected = True` in `AnalyticsDaily` with an explanatory diagnostic message.

---

## 5. Natural Language Processing & Voice Assistant

### 5.1 Voice Command Parsing
- **File**: `cloud_server/static/js/voice_search.js` ([L1-L220](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/static/js/voice_search.js#L1-L220))
- **Interface**: Web Speech API (`webkitSpeechRecognition`).
- **Entity Extraction**:
  - Copies: Regex pattern `/(?:print|make)?\s*(\d+)\s*(?:copies|copy)/i`
  - Color Mode: Matches keywords `color`, `colour`, `black and white`, `b&w`, `grayscale`
  - Duplex: Matches keywords `double sided`, `both sides`, `duplex`, `single sided`
  - Page Ranges: Extracts ranges such as `"pages 1 to 5"` -> `"1-5"`
