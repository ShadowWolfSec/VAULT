"""
PerformanceOptimizer | LazyAccountLoader | cached_icon_lookup
"""
import time
from functools import lru_cache


# ════════════════════════════════════════════════════════════
#  محسن الأداء (Cache)
# ════════════════════════════════════════════════════════════
class PerformanceOptimizer:
    """تخزين مؤقت لنتائج البحث والحسابات لتقليل الحسابات المتكررة"""

    def __init__(self, max_cache_size: int = 100):
        self.max_cache_size = max_cache_size
        self._account_cache = {}
        self._search_cache = {}
        self._last_cache_cleanup = time.time()
        self.cache_ttl = 300  # 5 دقائق

    def cleanup_cache(self):
        current_time = time.time()
        if current_time - self._last_cache_cleanup > self.cache_ttl:
            self._account_cache.clear()
            self._search_cache.clear()
            self._last_cache_cleanup = current_time

    def cache_account(self, account_id: str, account_data: dict):
        if len(self._account_cache) >= self.max_cache_size:
            oldest_key = next(iter(self._account_cache))
            del self._account_cache[oldest_key]
        self._account_cache[account_id] = {
            'data':      account_data,
            'timestamp': time.time()
        }

    def get_cached_account(self, account_id: str):
        if account_id in self._account_cache:
            cached = self._account_cache[account_id]
            if time.time() - cached['timestamp'] < self.cache_ttl:
                return cached['data']
            del self._account_cache[account_id]
        return None

    def cache_search_result(self, query: str, results: list):
        if len(self._search_cache) >= 50:
            oldest_key = next(iter(self._search_cache))
            del self._search_cache[oldest_key]
        self._search_cache[query.lower()] = {
            'results':   results,
            'timestamp': time.time()
        }

    def get_cached_search(self, query: str):
        query_lower = query.lower()
        if query_lower in self._search_cache:
            cached = self._search_cache[query_lower]
            if time.time() - cached['timestamp'] < self.cache_ttl:
                return cached['results']
            del self._search_cache[query_lower]
        return None


# ════════════════════════════════════════════════════════════
#  محمل تدريجي للحسابات (Lazy Loading)
# ════════════════════════════════════════════════════════════
class LazyAccountLoader:
    """يحمل الحسابات على دفعات لتحسين الأداء مع القوائم الكبيرة"""

    def __init__(self, vault_data: dict, batch_size: int = 50):
        self.vault_data = vault_data
        self.batch_size = batch_size
        self._loaded_accounts = []
        self._current_index = 0
        self.total_accounts = len(vault_data.get('accounts', []))

    def load_next_batch(self) -> list:
        if self._current_index >= self.total_accounts:
            return []
        accounts = self.vault_data.get('accounts', [])
        end_index = min(self._current_index + self.batch_size, self.total_accounts)
        batch = accounts[self._current_index:end_index]
        self._loaded_accounts.extend(batch)
        self._current_index = end_index
        return batch

    def get_all_accounts(self) -> list:
        if self._current_index < self.total_accounts:
            while self._current_index < self.total_accounts:
                self.load_next_batch()
        return self._loaded_accounts

    def search_accounts(self, query: str, optimizer: PerformanceOptimizer = None) -> list:
        """بحث فعال مع دعم التخزين المؤقت"""
        if optimizer:
            cached = optimizer.get_cached_search(query)
            if cached is not None:
                return cached

        results = []
        query_lower = query.lower()

        for account in self._loaded_accounts:
            if (query_lower in account.get('name', '').lower() or
                    query_lower in account.get('username', '').lower()):
                results.append(account)

        if not results and self._current_index < self.total_accounts:
            while self._current_index < self.total_accounts and len(results) < 20:
                for account in self.load_next_batch():
                    if (query_lower in account.get('name', '').lower() or
                            query_lower in account.get('username', '').lower()):
                        results.append(account)

        if optimizer and results:
            optimizer.cache_search_result(query, results)

        return results


# ════════════════════════════════════════════════════════════
#  أيقونات الحسابات (مخبأة)
# ════════════════════════════════════════════════════════════
@lru_cache(maxsize=128)
def cached_icon_lookup(name: str) -> str:
    """بحث مخبأ لأيقونات الخدمات الشائعة"""
    icons = {
        "gmail": "📧", "google": "📧", "github": "🐙",
        "twitter": "🐦", "x": "🐦", "facebook": "📘",
        "instagram": "📸", "amazon": "🛒", "aws": "☁️",
        "netflix": "🎬", "spotify": "🎵", "discord": "💬",
        "slack": "💼", "apple": "🍎", "bank": "🏦", "paypal": "💳"
    }
    n = name.lower()
    for k, v in icons.items():
        if k in n:
            return v
    return "🔑"
