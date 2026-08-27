import os
import json
import time
import requests
from typing import Optional, Dict, Any

class KISClient:
    """
    한국투자증권 (KIS Developers) 공식 Open API 클라이언트
    - 국내 지수 (코스피/코스닥) 실시간 시세
    - 투자자별 매매동향 (개인/외인/기관) 실시간 잠정/확정 수급
    - 실시간 거래대금/거래량 순위
    """
    def __init__(self, app_key: str = "", app_secret: str = "", is_mock: bool = True):
        self.app_key = app_key
        self.app_secret = app_secret
        self.is_mock = is_mock
        # 실전: https://openapi.koreainvestment.com:9443
        # 모의: https://openapivts.koreainvestment.com:29443
        self.base_url = "https://openapivts.koreainvestment.com:29443" if is_mock else "https://openapi.koreainvestment.com:9443"
        self.token = ""
        self.token_expired_at = 0

    def is_configured(self) -> bool:
        return bool(self.app_key and self.app_secret and len(self.app_key) > 10)

    def get_access_token(self) -> Optional[str]:
        if not self.is_configured():
            return None
        
        # Check cached token
        if self.token and time.time() < self.token_expired_at - 60:
            return self.token

        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            res = requests.post(url, headers=headers, data=json.dumps(body), timeout=5)
            if res.status_code == 200:
                data = res.json()
                self.token = data.get("access_token")
                # Token valid for 24 hours (86400s)
                expires_in = data.get("expires_in", 86400)
                self.token_expired_at = time.time() + expires_in
                return self.token
        except Exception as e:
            print(f"[KIS] Token issue error: {e}")
        return None

    def get_index_price(self, iscd: str = "0001") -> Optional[Dict[str, Any]]:
        """
        국내 지수 시세 조회 (0001: 코스피, 1001: 코스닥, 2001: 코스피200)
        """
        token = self.get_access_token()
        if not token:
            return None

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-index-price"
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKUP03500100", # 업종현재가
            "custtype": "P"
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "U",
            "FID_INPUT_ISCD": iscd
        }

        try:
            res = requests.get(url, headers=headers, params=params, timeout=3)
            if res.status_code == 200:
                out = res.json().get("output", {})
                price = float(out.get("bstp_nmix_prpr", "0"))
                chg = float(out.get("bstp_nmix_prdy_vrss", "0"))
                sign = out.get("prdy_vrss_sign", "3")
                if sign in ["4", "5"]: # 하락, 하한
                    chg = -abs(chg)
                rate = float(out.get("bstp_nmix_prdy_ctrt", "0"))
                if sign in ["4", "5"]:
                    rate = -abs(rate)
                return {
                    "price": price,
                    "change_val": chg,
                    "change_rate": rate
                }
        except Exception as e:
            print(f"[KIS] Index price error: {e}")
        return None

    def get_index_investor_trend(self, iscd: str = "0001") -> Optional[Dict[str, Any]]:
        """
        업종/지수별 투자자 매매동향 (개인, 외국인, 기관 순매수 대금 억원)
        """
        token = self.get_access_token()
        if not token:
            return None

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-investor"
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKUP03500200",
            "custtype": "P"
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "U",
            "FID_INPUT_ISCD": iscd
        }

        try:
            res = requests.get(url, headers=headers, params=params, timeout=3)
            if res.status_code == 200:
                out = res.json().get("output", {})
                # prsn_ntby_amt: 개인순매수금액, frgn_ntby_amt: 외국인순매수금액, orgn_ntby_amt: 기관순매수금액
                return {
                    "individual": int(out.get("prsn_ntby_amt", "0")),
                    "foreign": int(out.get("frgn_ntby_amt", "0")),
                    "institutional": int(out.get("orgn_ntby_amt", "0"))
                }
        except Exception as e:
            print(f"[KIS] Investor trend error: {e}")
        return None
