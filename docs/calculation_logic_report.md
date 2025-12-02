# BMS Difficulty Calculation Logic Report

This document details the internal logic of `calc.py`, which determines the difficulty level of a BMS chart.

## 1. Overview

The difficulty calculation pipeline consists of 5 main steps:
1.  **Metric Aggregation**: Combining various raw metrics (NPS, Strain, etc.) into a single "Load" value ($b_t$) for each time window.
2.  **Load Processing**: Applying "Soft Cap" to limit extreme spikes and calculating Endurance ($F$) and Burst ($P$) components using Exponential Moving Averages (EMA).
3.  **Raw Difficulty ($D_0$)**: Combining $F$, $P$, and Variance ($V$) into a single raw difficulty score using an L5 Norm.
4.  **Length Bonus**: Adjusting the score based on the chart's duration to account for stamina drain.
5.  **Level Mapping**: Converting the final $D_{pattern}$ score into a 1-25 Level scale.

---

## 2. Step-by-Step Calculation

### Step 1: Window Load Calculation ($b_t$)

For each 1-second window $t$, we calculate the total load $b_t$ as a weighted sum of various metrics.

$$
b_t = \alpha \cdot \text{NPS}' + \beta \cdot \text{LN} + \gamma \cdot \text{Jack} + \delta \cdot \text{Roll} + \eta \cdot \text{Alt} + \theta \cdot \text{Hand}
$$

**Parameters (Optimized):**
-   $\alpha$ (NPS Weight): **1.1748** (Primary factor)
-   $\beta$ (LN Weight): 1.0
-   $\gamma$ (Jack Weight): 1.0
-   $\delta$ (Roll Weight): 1.0
-   $\eta$ (Alt Weight): **0.1000** (Low impact)
-   $\theta$ (Hand Strain Weight): **2.0000** (High impact for density)

**NPS Scaling:**
If NPS > 40, it is scaled non-linearly to prevent excessive inflation:
$$
\text{NPS}' = 40 + (\text{NPS} - 40)^{1.2}
$$

### Step 2: Soft Cap & EMA

**Soft Cap:**
To prevent a single impossible second from skewing the entire chart's difficulty, we apply a "Soft Cap" to $b_t$.
-   **Threshold ($T$)**: 60.0
-   **Range ($C$)**: 30.0

If $b_t > T$:
$$
b_t' = T + (b_t - T) \cdot \frac{C}{C + (b_t - T)}
$$
*This ensures $b_t$ never exceeds $T+C$ (90.0).*

**Endurance & Burst:**
We use two EMAs (Exponential Moving Averages) to capture different aspects of difficulty:
-   **Endurance ($F$)**: Mean of Slow EMA ($\lambda_L = 0.3$). Represents overall stamina requirement.
-   **Burst ($P$)**: Max of Fast EMA ($\lambda_S = 0.8$). Represents the hardest peak difficulty.

### Step 3: Raw Difficulty ($D_0$)

We combine $F$, $P$, and Variance ($V$) into a single score using an **L5 Norm**. The L5 Norm emphasizes the largest component (usually Peak) more than a simple average.

$$
D_0 = \left( |w_F \cdot F|^5 + |w_P \cdot P|^5 + |w_V \cdot V|^5 \right)^{1/5}
$$

-   $w_F = 1.0$
-   $w_P = 1.0$
-   $w_V = 0.2$

### Step 4: Length Bonus

Longer charts require more stamina. We apply a bonus multiplier based on duration.

-   **Base Duration**: 60 seconds
-   **Factor**: +8% per doubling of duration beyond 60s.

$$
\text{Bonus} = 1.0 + 0.08 \cdot \log_2(\max(\text{Duration}, 60) / 60)
$$

$$
D_{pattern} = D_0 \cdot \text{Bonus}
$$

### Step 5: Level Mapping (1-25)

Finally, we map the raw $D_{pattern}$ to a user-friendly Level (1-25).
Based on our calibration with the `10K2S` and `Revive` datasets, we use a linear mapping.

-   $D_{min} = 0.0$ (Level 1)
-   $D_{max} = 150.0$ (Level 25)

$$
\text{Level} \approx \frac{D_{pattern}}{6.25} + 1
$$

*(Exact formula uses a normalized interpolation, but it's effectively linear due to $\gamma=1.0$)*

---

## 3. Summary of Optimized Weights

The following weights were found to minimize error (MAE 2.10) against 900+ labeled charts:

| Parameter | Value | Description |
| :--- | :--- | :--- |
| **Alpha (NPS)** | **1.17** | Density is the main driver of difficulty. |
| **Theta (Hand)** | **2.00** | One-handed density (strain) is critical for 10K/14K. |
| **Eta (Alt)** | **0.10** | Hand alternation is less important than raw density. |
| **D_max** | **150.0** | The scale of raw difficulty extends up to ~150 for Level 25. |
