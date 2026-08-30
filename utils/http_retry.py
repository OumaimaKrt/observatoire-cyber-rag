# utils/http_retry.py
import time
from typing import Optional
import requests

from utils.logger import get_logger

logger = get_logger("http_retry")


def get_with_retry(
    url: str,
    *,
    tentatives: int = 3,
    timeout: int = 30,
    backoff_seconds: float = 3.0,
    logger_prefix: str = "",
    **kwargs,
) -> Optional[requests.Response]:

    derniere_erreur = None

    for tentative in range(1, tentatives + 1):
        try:
            resp = requests.get(url, timeout=timeout, **kwargs)

            # Erreur serveur (5xx) : transitoire, on retente.
            if resp.status_code >= 500:
                derniere_erreur = f"HTTP {resp.status_code}"
                logger.warning(
                    f"{logger_prefix}: tentative {tentative}/{tentatives} "
                    f"échouée ({derniere_erreur}) — {url}"
                )
            else:
                # Inclut les erreurs 4xx : on laisse raise_for_status()
                # décider, l'appelant doit voir l'erreur immédiatement.
                if tentative > 1:
                    logger.info(
                        f"{logger_prefix}: réussi à la tentative {tentative}/{tentatives}"
                    )
                return resp

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            derniere_erreur = str(e)
            logger.warning(
                f"{logger_prefix}: tentative {tentative}/{tentatives} "
                f"échouée ({type(e).__name__}: {e}) — {url}"
            )

        if tentative < tentatives:
            time.sleep(backoff_seconds * tentative)

    logger.error(
        f"{logger_prefix}: échec après {tentatives} tentative(s) — "
        f"dernière erreur : {derniere_erreur}"
    )
    return None