# -*- coding: utf-8 -*-
"""
ClawCloud 自动登录脚本（已修复 OAuth 重定向判断）
"""

import base64
import os
import re
import sys
import time
from urllib.parse import urlparse

import requests
from playwright.sync_api import sync_playwright

LOGIN_ENTRY_URL = "https://console.run.claw.cloud"
SIGNIN_URL = f"{LOGIN_ENTRY_URL}/signin"
DEVICE_VERIFY_WAIT = 30
TWO_FACTOR_WAIT = int(os.environ.get("TWO_FACTOR_WAIT", "120"))


class Telegram:
    def __init__(self):
        self.token = os.environ.get('TG_BOT_TOKEN')
        self.chat_id = os.environ.get('TG_CHAT_ID')
        self.ok = bool(self.token and self.chat_id)

    def send(self, msg):
        if not self.ok:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                data={"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"},
                timeout=30
            )
        except:
            pass

    def photo(self, path, caption=""):
        if not self.ok or not os.path.exists(path):
            return
        try:
            with open(path, 'rb') as f:
                requests.post(
                    f"https://api.telegram.org/bot{self.token}/sendPhoto",
                    data={"chat_id": self.chat_id, "caption": caption[:1024]},
                    files={"photo": f},
                    timeout=60
                )
        except:
            pass


class AutoLogin:
    def __init__(self):
        self.username = os.environ.get('GH_USERNAME')
        self.password = os.environ.get('GH_PASSWORD')
        self.logs = []
        self.shots = []
        self.detected_region = None
        self.region_base_url = None

    def log(self, msg, level="INFO"):
        icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "STEP": "🔹"}
        line = f"{icons.get(level, '•')} {msg}"
        print(line)
        self.logs.append(line)

    def detect_region(self, url):
        try:
            parsed = urlparse(url)
            host = parsed.netloc
            if host.endswith('.console.claw.cloud'):
                region = host.replace('.console.claw.cloud', '')
                self.detected_region = region
                self.region_base_url = f"https://{host}"
                self.log(f"检测到区域: {region}", "SUCCESS")
        except:
            pass

    def oauth(self, page):
        if 'github.com/login/oauth/authorize' in page.url:
            try:
                page.locator('button:has-text("Authorize")').first.click()
            except:
                pass

    def wait_redirect(self, page, wait=60):
        """等待 OAuth 完成，不强依赖 URL 变化"""
        self.log("等待 OAuth 完成...", "STEP")

        for i in range(wait):
            url = page.url

            if 'claw.cloud' in url and 'signin' not in url.lower():
                self.log("已在 ClawCloud，登录成功", "SUCCESS")
                self.detect_region(url)
                return True

            if 'github.com/login/oauth/authorize' in url:
                self.oauth(page)

            if i % 10 == 0:
                try:
                    page.goto(LOGIN_ENTRY_URL, timeout=30000)
                    page.wait_for_load_state('networkidle', timeout=15000)
                    if 'signin' not in page.url.lower():
                        self.log("主动验证成功（Cookie 已生效）", "SUCCESS")
                        self.detect_region(page.url)
                        return True
                except:
                    pass
                self.log(f"  等待... ({i}秒)")

            time.sleep(1)

        self.log("OAuth 完成但未检测到成功状态", "ERROR")
        return False

    def run(self):
        if not self.username or not self.password:
            self.log("缺少 GitHub 凭据", "ERROR")
            sys.exit(1)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = browser.new_context()
            page = context.new_page()

            self.log("打开 ClawCloud 登录页", "STEP")
            page.goto(SIGNIN_URL, timeout=60000)
            page.wait_for_load_state('networkidle')

            self.log("点击 GitHub 登录", "STEP")
            page.locator('button:has-text("GitHub"), a:has-text("GitHub")').first.click()
            page.wait_for_load_state('networkidle')

            self.log("填写 GitHub 凭据", "STEP")
            page.locator('input[name="login"]').fill(self.username)
            page.locator('input[name="password"]').fill(self.password)
            page.locator('input[type="submit"]').click()

            page.wait_for_load_state('networkidle')

            if not self.wait_redirect(page):
                sys.exit(1)

            self.log("🎉 登录流程完成", "SUCCESS")
            browser.close()


if __name__ == "__main__":
    AutoLogin().run()
