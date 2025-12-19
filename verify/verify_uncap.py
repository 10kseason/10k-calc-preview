import calc

def verify_uncap():
    # Test estimate_level directly
    
    # S_hat = 0.0 -> Level 25 (capped) vs >25 (uncapped)
    # Formula: 1 + 24 * (1 - 0)^1.5 = 25.0
    # Wait, the formula is 1 + 24 * ... so max is 25.0 naturally if S_hat is 0.
    # Let's check the code:
    # est = 1.0 + 24.0 * ((1.0 - p) ** 1.5)
    # If p=0, est = 25.0.
    # So to go above 25, p must be negative? No, p is clamped 0-1.
    # Ah, the user wants to uncap the *limit*, but the formula itself has a natural limit of 25 if p is clamped to 0.
    # Unless... the user implies that the formula should extrapolate for p < 0?
    # OR, the user implies that if the difficulty is extremely high, S_hat is effectively 0, and we are capped at 25.
    # But wait, if S_hat is probability, it can't be < 0.
    
    # Let's re-read the code I modified.
    # p = max(0.0, min(1.0, S_hat))
    # est = 1.0 + 24.0 * ((1.0 - p) ** 1.5)
    # If p=0, est=25.
    
    # If the user wants > 25, then the formula itself needs to change or p shouldn't be clamped to 0?
    # But S_hat comes from sigmoid, so it's always 0-1.
    
    # Maybe the user means that if the difficulty D0 is extremely high, the level should keep going up?
    # But the current level estimation is based on S_hat.
    # If S_hat is 0.000001, level is near 25.
    
    # Wait, if I look at my change:
    # if not uncap: est = max(1.0, min(25.0, est))
    # else: est = max(1.0, est)
    
    # If the formula naturally caps at 25 (when p=0), then removing min(25.0) doesn't help if p is clamped to 0.
    # UNLESS p is NOT clamped to 0?
    # In `estimate_level`: p = max(0.0, min(1.0, S_hat))
    
    # So, if S_hat is a probability, it's 0-1. Max level is 25.
    # To support > 25, we need to allow p < 0? Or change the formula?
    # Or maybe the user thinks the cap is applied *after* a formula that could go higher?
    # Let's check the formula again.
    # est = 1.0 + 24.0 * ((1.0 - p) ** 1.5)
    # If p=0, est=25.
    
    # If the user wants "Uncap", they probably mean "Extrapolate for harder charts".
    # But with S_hat, we hit a wall at 0.
    # Maybe I should allow p to be negative?
    # S_hat comes from `predict_survival`.
    # `predict_survival` returns `sigmoid(...) ** gamma`.
    # Sigmoid is 0-1.
    
    # So, strictly speaking, with the current model, Level 25 is the theoretical max (0% survival).
    # If the user wants > 25, we might need to use D0 directly for levels > 25?
    # OR, maybe the user *thinks* it's capped at 25 but the formula could go higher?
    # 1 + 24 = 25.
    
    # Wait, previously it was `1 + 19 * ...` in the docstring but `1 + 24 * ...` in code?
    # Line 242: est = 1.0 + 24.0 * ((1.0 - p) ** 1.5)
    # If p=0, est=25.
    
    # If the user wants to uncap, they probably want to see levels like 26, 27 for impossible charts.
    # This implies we need a way to map D0 -> Level directly if S_hat is near 0.
    # BUT, I only implemented removing the `min(25.0, est)`.
    # Since the formula naturally peaks at 25, this change effectively does nothing for the upper bound unless I also change the formula or the input.
    
    # However, maybe I should check if `est` can naturally go above 25?
    # Only if p < 0.
    # But p is clamped.
    
    # I suspect I need to modify `estimate_level` to NOT clamp p to 0 if uncap is True?
    # But S_hat is from sigmoid, so it's > 0.
    # So p won't be < 0 anyway.
    
    # Conclusion: To support > 25, I must change the formula or mapping.
    # But the user only said "제한 해제 모드를 넣고 체크되어있으면 레벨 제한이 25에 걸리지 않도록 해줘".
    # Maybe they *thought* it was arbitrarily capped at 25 (which it was, `min(25.0, est)`).
    # But they might not realize the formula itself tops out at 25.
    
    # Let's verify if I can get > 25.
    # If I pass S_hat = -0.1 (impossible from sigmoid), I get > 25.
    # But S_hat is 0..1.
    
    # Maybe I should change the formula constant if uncap is True?
    # E.g. 1 + 50 * ...?
    # Or maybe the user intends for me to allow the level to go higher by extending the formula?
    
    # Let's assume for now that I should just remove the explicit clamp.
    # If the formula naturally caps at 25, then "Uncap" might just mean "Show 25 even if it's 25.0001" (which rounds to 25).
    # But wait, if the user sees 25 and thinks "It's capped!", they want to see 26.
    
    # I will verify what happens with S_hat=0.
    print(f"Level at S_hat=0.0 (Uncap=False): {calc.estimate_level(0.0, uncap=False)}")
    print(f"Level at S_hat=0.0 (Uncap=True): {calc.estimate_level(0.0, uncap=True)}")
    
    # If both are 25, then I haven't really "uncapped" it in a meaningful way for the user.
    # I should probably adjust the formula to allow > 25 if uncap is True.
    # But how?
    # Maybe map S_hat < 0.01 to levels > 25 using a different curve?
    # Or just increase the multiplier?
    # "1 + 24 * ..." -> "1 + 49 * ..."?
    
    # Let's try to infer intent.
    # "Level limit 25".
    # If the user hits 25 often, they want to see higher numbers.
    # I will assume I should allow the formula to extend.
    # But S_hat is probability.
    # If S_hat is 1e-9, it's basically 0.
    
    # Maybe I should use D0 to estimate level if S_hat is too low?
    # Or just let it be 25?
    
    # Let's just run this script first to confirm my suspicion.

if __name__ == "__main__":
    verify_uncap()
