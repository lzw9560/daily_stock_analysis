# -*- coding: utf-8 -*-
"""Adapters for factor pipeline backends.

The adapter layer prefers real Qlib / LightGBM / SHAP integrations when the
packages are installed, and falls back to a deterministic skeleton when they
are unavailable. This keeps Phase 2 opt-in and deployable in minimal envs.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd


@dataclass(frozen=True)
class FactorModelArtifacts:
    model_name: str
    trained: bool
    backend: str
    feature_names: List[str]
    importance: Dict[str, float]
    shap_values: Dict[str, float]
    training_summary: Dict[str, Any]
    monitoring_summary: Dict[str, Any]
    traces: Dict[str, Any]


@dataclass(frozen=True)
class _FamilyResult:
    family: str
    factor_scores: Dict[str, float]
    factor_score: float
    model_artifacts: Dict[str, Any]
    training_summary: Dict[str, Any]
    monitoring_summary: Dict[str, Any]
    feature_names: List[str]
    traces: Dict[str, Any]


class FactorBackendAdapter:
    """Backend adapter with real-dependency preference and skeleton fallback."""

    def __init__(self) -> None:
        self.backend = self._detect_backend()

    @staticmethod
    def _detect_backend() -> str:
        try:
            import qlib  # noqa: F401
            import lightgbm  # noqa: F401
            import shap  # noqa: F401
            return "real"
        except Exception:
            return "skeleton"

    def build_factor_rows(
        self,
        *,
        screening_date: date,
        strategy: str,
        candidate_code: str,
        candidate_rank: int,
        factor_specs: Sequence[Dict[str, Any]],
        train_days: int,
        valid_days: int,
        test_days: int,
        shap_sample_size: int,
        instruments: str,
        region: str,
    ) -> Dict[str, Any]:
        if self.backend == "real":
            try:
                return self._build_real_factor_rows(
                    screening_date=screening_date,
                    strategy=strategy,
                    candidate_code=candidate_code,
                    candidate_rank=candidate_rank,
                    factor_specs=factor_specs,
                    train_days=train_days,
                    valid_days=valid_days,
                    test_days=test_days,
                    shap_sample_size=shap_sample_size,
                    instruments=instruments,
                    region=region,
                )
            except Exception as exc:
                return self._build_skeleton_factor_rows(
                    screening_date=screening_date,
                    strategy=strategy,
                    candidate_code=candidate_code,
                    candidate_rank=candidate_rank,
                    factor_specs=factor_specs,
                    backend="real_fallback",
                    backend_error=str(exc),
                    train_days=train_days,
                    valid_days=valid_days,
                    test_days=test_days,
                    shap_sample_size=shap_sample_size,
                )
        return self._build_skeleton_factor_rows(
            screening_date=screening_date,
            strategy=strategy,
            candidate_code=candidate_code,
            candidate_rank=candidate_rank,
            factor_specs=factor_specs,
            train_days=train_days,
            valid_days=valid_days,
            test_days=test_days,
            shap_sample_size=shap_sample_size,
        )

    def _build_real_factor_rows(
        self,
        *,
        screening_date: date,
        strategy: str,
        candidate_code: str,
        candidate_rank: int,
        factor_specs: Sequence[Dict[str, Any]],
        train_days: int,
        valid_days: int,
        test_days: int,
        shap_sample_size: int,
        instruments: str,
        region: str,
    ) -> Dict[str, Any]:
        qlib_module, alpha158_cls, alpha360_cls, lgbm_regressor_cls, shap_module = self._import_real_dependencies()
        provider_uri = os.getenv("FACTOR_QLIB_PROVIDER_URI", "").strip()
        if not provider_uri:
            raise RuntimeError("FACTOR_QLIB_PROVIDER_URI is required for the real factor backend")

        self._init_qlib(qlib_module, provider_uri=provider_uri, region_name=region)

        train_start, train_end, valid_start, valid_end, test_start, test_end = self._build_date_windows(
            screening_date,
            train_days=train_days,
            valid_days=valid_days,
            test_days=test_days,
        )
        family_results = [
            self._run_family_pipeline(
                family_name="alpha158",
                handler_cls=alpha158_cls,
                lgbm_regressor_cls=lgbm_regressor_cls,
                shap_module=shap_module,
                factor_specs=[spec for spec in factor_specs if str(spec.get("name", "")).startswith("alpha158")],
                handler_kwargs={
                    "start_time": train_start.isoformat(),
                    "end_time": test_end.isoformat(),
                    "fit_start_time": train_start.isoformat(),
                    "fit_end_time": train_end.isoformat(),
                    "instruments": instruments,
                },
                split_kwargs={
                    "train_start": train_start,
                    "train_end": train_end,
                    "valid_start": valid_start,
                    "valid_end": valid_end,
                    "test_start": test_start,
                    "test_end": test_end,
                },
                shap_sample_size=shap_sample_size,
            ),
            self._run_family_pipeline(
                family_name="alpha360",
                handler_cls=alpha360_cls,
                lgbm_regressor_cls=lgbm_regressor_cls,
                shap_module=shap_module,
                factor_specs=[spec for spec in factor_specs if str(spec.get("name", "")).startswith("alpha360")],
                handler_kwargs={
                    "start_time": train_start.isoformat(),
                    "end_time": test_end.isoformat(),
                    "fit_start_time": train_start.isoformat(),
                    "fit_end_time": train_end.isoformat(),
                    "instruments": instruments,
                },
                split_kwargs={
                    "train_start": train_start,
                    "train_end": train_end,
                    "valid_start": valid_start,
                    "valid_end": valid_end,
                    "test_start": test_start,
                    "test_end": test_end,
                },
                shap_sample_size=shap_sample_size,
            ),
        ]

        merged = self.merge_backend_payloads(family_results)
        merged["backend"] = "real"
        merged["traces"] = {
            result.family: result.traces for result in family_results
        }
        merged["training_summary"]["backend"] = "real"
        merged["training_summary"]["status"] = "trained"
        merged["training_summary"]["sample_size"] = sum(result.training_summary.get("sample_size", 0) for result in family_results)
        merged["monitoring_summary"]["decay_alert"] = bool(
            any(result.monitoring_summary.get("decay_alert") for result in family_results)
        )
        return merged

    def _run_family_pipeline(
        self,
        *,
        family_name: str,
        handler_cls: Any,
        lgbm_regressor_cls: Any,
        shap_module: Any,
        factor_specs: Sequence[Dict[str, Any]],
        handler_kwargs: Dict[str, Any],
        split_kwargs: Dict[str, date],
        shap_sample_size: int,
    ) -> _FamilyResult:
        handler = self._instantiate_handler(handler_cls, handler_kwargs)
        split_data = self._get_split_data(handler, split_kwargs)
        x_train, y_train, x_valid, y_valid, x_test, y_test = self._normalize_split_data(split_data)

        if x_train.empty or y_train.empty:
            raise RuntimeError(f"{family_name}: empty training data")

        model = lgbm_regressor_cls(
            n_estimators=self._resolve_int_env("FACTOR_PIPELINE_LGBM_ESTIMATORS", 256),
            learning_rate=self._resolve_float_env("FACTOR_PIPELINE_LGBM_LEARNING_RATE", 0.05),
            num_leaves=self._resolve_int_env("FACTOR_PIPELINE_LGBM_NUM_LEAVES", 31),
            random_state=42,
        )
        model.fit(x_train, y_train)

        valid_pred = self._predict_series(model, x_valid)
        test_pred = self._predict_series(model, x_test)
        train_label = self._series_to_numeric(y_train)
        valid_label = self._series_to_numeric(y_valid)
        test_label = self._series_to_numeric(y_test)
        train_pred = self._predict_series(model, x_train)

        shap_values, shap_trace = self._compute_shap_values(
            shap_module,
            model,
            x_train,
            x_valid,
            shap_sample_size=shap_sample_size,
        )
        feature_importance = self._build_importance_map(x_train.columns.tolist(), getattr(model, "feature_importances_", []))
        shap_importance = self._build_shap_importance_map(x_valid.columns.tolist(), shap_values)

        factor_scores = self._assign_factor_scores(factor_specs, feature_importance, shap_importance)
        factor_score = round(sum(factor_scores.values()) / len(factor_scores), 4) if factor_scores else 0.0
        monitoring_summary = self._build_monitoring_summary(
            train_label=train_label,
            train_pred=train_pred,
            valid_label=valid_label,
            valid_pred=valid_pred,
            test_label=test_label,
            test_pred=test_pred,
        )
        training_summary = {
            "algorithm": "LightGBM",
            "rolling": True,
            "enabled": True,
            "backend": "real",
            "status": "trained",
            "sample_size": int(len(x_train)),
            "feature_count": int(len(x_train.columns)),
            "valid_size": int(len(x_valid)),
            "test_size": int(len(x_test)),
            "train_window_days": int((split_kwargs["train_end"] - split_kwargs["train_start"]).days),
            "valid_window_days": int((split_kwargs["valid_end"] - split_kwargs["valid_start"]).days),
            "test_window_days": int((split_kwargs["test_end"] - split_kwargs["test_start"]).days),
            "shap_sample_size": shap_sample_size,
        }
        model_artifacts = {
            "backend": "real",
            "model_name": type(model).__name__,
            "trained": True,
            "feature_names": x_train.columns.tolist(),
            "importance": feature_importance,
            "shap_values": shap_importance,
            "shap_trace": shap_trace,
            "shap_feature_count": len(shap_importance),
            "train_prediction_mean": float(train_pred.mean()) if len(train_pred) else None,
            "valid_prediction_mean": float(valid_pred.mean()) if len(valid_pred) else None,
            "test_prediction_mean": float(test_pred.mean()) if len(test_pred) else None,
        }
        traces = {
            "handler": self._build_trace_summary(handler, split_kwargs),
            "data_windows": {
                "train": {"start": split_kwargs["train_start"].isoformat(), "end": split_kwargs["train_end"].isoformat()},
                "valid": {"start": split_kwargs["valid_start"].isoformat(), "end": split_kwargs["valid_end"].isoformat()},
                "test": {"start": split_kwargs["test_start"].isoformat(), "end": split_kwargs["test_end"].isoformat()},
            },
            "samples": {
                "train": int(len(x_train)),
                "valid": int(len(x_valid)),
                "test": int(len(x_test)),
            },
            "shap": shap_trace,
        }
        return _FamilyResult(
            family=family_name,
            factor_scores=factor_scores,
            factor_score=factor_score,
            model_artifacts=model_artifacts,
            training_summary=training_summary,
            monitoring_summary=monitoring_summary,
            feature_names=x_train.columns.tolist(),
            traces=traces,
        )

    def _instantiate_handler(self, handler_cls: Any, handler_kwargs: Dict[str, Any]) -> Any:
        try:
            return handler_cls(**handler_kwargs)
        except TypeError:
            fallback_kwargs = {
                "start_date": handler_kwargs["start_time"],
                "end_date": handler_kwargs["end_time"],
                "market": handler_kwargs.get("instruments", "csi300"),
            }
            return handler_cls(**fallback_kwargs)

    def _get_split_data(self, handler: Any, split_kwargs: Dict[str, date]) -> Tuple[Any, Any, Any, Any, Any, Any]:
        call_variants = [
            {
                "train_start_date": split_kwargs["train_start"].isoformat(),
                "train_end_date": split_kwargs["train_end"].isoformat(),
                "validate_start_date": split_kwargs["valid_start"].isoformat(),
                "validate_end_date": split_kwargs["valid_end"].isoformat(),
                "test_start_date": split_kwargs["test_start"].isoformat(),
                "test_end_date": split_kwargs["test_end"].isoformat(),
            },
            {
                "train_start_date": split_kwargs["train_start"].isoformat(),
                "train_end_date": split_kwargs["train_end"].isoformat(),
                "valid_start_date": split_kwargs["valid_start"].isoformat(),
                "valid_end_date": split_kwargs["valid_end"].isoformat(),
                "test_start_date": split_kwargs["test_start"].isoformat(),
                "test_end_date": split_kwargs["test_end"].isoformat(),
            },
            {
                "train_start": split_kwargs["train_start"].isoformat(),
                "train_end": split_kwargs["train_end"].isoformat(),
                "valid_start": split_kwargs["valid_start"].isoformat(),
                "valid_end": split_kwargs["valid_end"].isoformat(),
                "test_start": split_kwargs["test_start"].isoformat(),
                "test_end": split_kwargs["test_end"].isoformat(),
            },
        ]
        last_exc: Optional[Exception] = None
        for kwargs in call_variants:
            try:
                return handler.get_split_data(**kwargs)
            except TypeError as exc:
                last_exc = exc
                continue
        raise RuntimeError(f"handler.get_split_data signature mismatch: {last_exc}")

    def _normalize_split_data(self, split_data: Any) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
        if not isinstance(split_data, (tuple, list)) or len(split_data) != 6:
            raise RuntimeError("Unexpected Qlib split data shape")
        x_train, y_train, x_valid, y_valid, x_test, y_test = split_data
        return (
            self._ensure_frame(x_train),
            self._ensure_series(y_train),
            self._ensure_frame(x_valid),
            self._ensure_series(y_valid),
            self._ensure_frame(x_test),
            self._ensure_series(y_test),
        )

    @staticmethod
    def _ensure_frame(value: Any) -> pd.DataFrame:
        if isinstance(value, pd.DataFrame):
            return value.copy()
        if isinstance(value, pd.Series):
            return value.to_frame().copy()
        return pd.DataFrame(value).copy()

    @staticmethod
    def _ensure_series(value: Any) -> pd.Series:
        if isinstance(value, pd.Series):
            return value.copy()
        if isinstance(value, pd.DataFrame):
            if value.shape[1] == 1:
                return value.iloc[:, 0].copy()
            return value.iloc[:, 0].copy()
        return pd.Series(value).copy()

    @staticmethod
    def _series_to_numeric(series: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(series, errors="coerce")
        return numeric.dropna()

    @staticmethod
    def _predict_series(model: Any, frame: pd.DataFrame) -> pd.Series:
        if frame.empty:
            return pd.Series(dtype=float)
        predictions = model.predict(frame)
        return pd.Series(predictions, index=frame.index if hasattr(frame, "index") else None).astype(float)

    def _compute_shap_values(
        self,
        shap_module: Any,
        model: Any,
        x_train: pd.DataFrame,
        x_valid: pd.DataFrame,
        *,
        shap_sample_size: int,
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        if x_valid.empty:
            zeros = {column: 0.0 for column in x_train.columns}
            return zeros, {"sample_size": 0, "source": "empty_validation"}
        sample_size = min(max(shap_sample_size, 1), len(x_train)) if len(x_train) else 0
        background = x_train.head(sample_size) if sample_size else x_train
        explainer = shap_module.TreeExplainer(model, background, feature_perturbation="auto")
        shap_frame = x_valid.head(min(shap_sample_size, len(x_valid)))
        shap_values = explainer.shap_values(shap_frame)
        if isinstance(shap_values, list):
            shap_values = shap_values[0]
        shap_df = pd.DataFrame(shap_values, columns=shap_frame.columns)
        return shap_df.abs().mean().to_dict(), {
            "sample_size": int(len(shap_frame)),
            "background_size": int(len(background)),
            "source": "tree_explainer",
        }

    @staticmethod
    def _build_importance_map(feature_names: Sequence[str], importance_values: Sequence[Any]) -> Dict[str, float]:
        importance_list = list(importance_values) if importance_values is not None else []
        return {
            str(feature_names[i]): float(importance_list[i])
            for i in range(min(len(feature_names), len(importance_list)))
        }

    @staticmethod
    def _build_shap_importance_map(feature_names: Sequence[str], shap_importance: Dict[str, float]) -> Dict[str, float]:
        return {str(name): float(shap_importance.get(name, 0.0)) for name in feature_names}

    @staticmethod
    def _assign_factor_scores(
        factor_specs: Sequence[Dict[str, Any]],
        feature_importance: Dict[str, float],
        shap_importance: Dict[str, float],
    ) -> Dict[str, float]:
        source_values = list(shap_importance.values()) or list(feature_importance.values()) or [0.0]
        factor_scores: Dict[str, float] = {}
        for index, spec in enumerate(factor_specs):
            name = str(spec.get("name") or f"factor_{index}")
            factor_scores[name] = round(float(source_values[index % len(source_values)]), 4)
        return factor_scores

    @staticmethod
    def _build_monitoring_summary(
        *,
        train_label: pd.Series,
        train_pred: pd.Series,
        valid_label: pd.Series,
        valid_pred: pd.Series,
        test_label: pd.Series,
        test_pred: pd.Series,
    ) -> Dict[str, Any]:
        def _corr(left: pd.Series, right: pd.Series) -> Optional[float]:
            frame = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
            if len(frame) < 2:
                return None
            value = frame["left"].corr(frame["right"])
            return float(value) if value == value else None

        train_ic = _corr(train_pred, train_label)
        valid_ic = _corr(valid_pred, valid_label)
        test_ic = _corr(test_pred, test_label)
        ic_values = [value for value in [train_ic, valid_ic, test_ic] if value is not None]
        decay = None
        if train_ic is not None and valid_ic is not None:
            decay = max(0.0, 1.0 - abs(train_ic - valid_ic))
        elif valid_ic is not None:
            decay = max(0.0, 1.0 - abs(valid_ic))
        ir = None
        if ic_values:
            mean_ic = sum(ic_values) / len(ic_values)
            variance = sum((value - mean_ic) ** 2 for value in ic_values) / len(ic_values)
            std_dev = variance ** 0.5
            ir = float(mean_ic / std_dev) if std_dev else 0.0
        return {
            "ic": valid_ic if valid_ic is not None else train_ic,
            "ir": ir,
            "decay": decay,
            "decay_alert": bool(decay is not None and decay < 0.2),
            "train_ic": train_ic,
            "valid_ic": valid_ic,
            "test_ic": test_ic,
        }

    @staticmethod
    def _build_date_windows(
        screening_date: date,
        *,
        train_days: int,
        valid_days: int,
        test_days: int,
    ) -> Tuple[date, date, date, date, date, date]:
        test_end = screening_date
        test_start = screening_date - timedelta(days=test_days)
        valid_end = test_start - timedelta(days=1)
        valid_start = valid_end - timedelta(days=valid_days)
        train_end = valid_start - timedelta(days=1)
        train_start = train_end - timedelta(days=train_days)
        return train_start, train_end, valid_start, valid_end, test_start, test_end

    @staticmethod
    def _init_qlib(qlib_module: Any, *, provider_uri: str, region_name: str) -> None:
        try:
            from qlib.constant import REG_CN, REG_US  # type: ignore
        except Exception:
            from qlib.config import REG_CN, REG_US  # type: ignore

        region_map = {"cn": REG_CN, "us": REG_US}
        region = region_map.get(region_name.lower())
        if region is None:
            raise ValueError(f"Unsupported FACTOR_QLIB_REGION={region_name!r}")
        qlib_module.init(provider_uri=provider_uri, region=region)

    @staticmethod
    def _import_real_dependencies() -> Tuple[Any, Any, Any, Any, Any]:
        import qlib  # type: ignore

        try:
            from qlib.contrib.data.handler import Alpha158, Alpha360  # type: ignore
        except Exception:
            from qlib.contrib.estimator.handler import Alpha158, Alpha360  # type: ignore

        from lightgbm import LGBMRegressor  # type: ignore
        import shap  # type: ignore

        return qlib, Alpha158, Alpha360, LGBMRegressor, shap

    def _build_skeleton_factor_rows(
        self,
        *,
        screening_date: date,
        strategy: str,
        candidate_code: str,
        candidate_rank: int,
        factor_specs: Sequence[Dict[str, Any]],
        train_days: int,
        valid_days: int,
        test_days: int,
        shap_sample_size: int,
        backend: str = "skeleton",
        backend_error: Optional[str] = None,
    ) -> Dict[str, Any]:
        seed = f"{screening_date}:{strategy}:{candidate_code}:{candidate_rank}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        values = [int(digest[i : i + 8], 16) for i in range(0, min(len(digest), 40), 8)]
        feature_names = [str(spec.get("name")) for spec in factor_specs]
        factor_values = {}
        for i, spec in enumerate(factor_specs):
            value = round(((values[i % len(values)] % 2000) / 100.0) - 10.0, 4)
            factor_values[str(spec.get("name"))] = value
        importance = {name: abs(value) for name, value in factor_values.items()}
        shap_values = {name: round(value / 2.0, 4) for name, value in factor_values.items()}
        training_summary = {
            "algorithm": "LightGBM",
            "rolling": True,
            "enabled": False,
            "backend": backend,
            "status": "skeleton",
            "sample_size": len(factor_specs),
            "train_window_days": train_days,
            "valid_window_days": valid_days,
            "test_window_days": test_days,
            "shap_sample_size": shap_sample_size,
        }
        monitoring_summary = {
            "ic": round(sum(factor_values.values()) / len(factor_values) / 100.0, 4) if factor_values else None,
            "ir": 0.0,
            "decay": round(max(0.0, 1.0 - sum(importance.values()) / (len(importance) * 10.0)) if importance else 0.0, 4),
            "decay_alert": False,
        }
        model_artifacts = FactorModelArtifacts(
            model_name="LightGBM",
            trained=False,
            backend=backend,
            feature_names=feature_names,
            importance=importance,
            shap_values=shap_values,
            training_summary=training_summary,
            monitoring_summary=monitoring_summary,
            traces={
                "train_window_days": train_days,
                "valid_window_days": valid_days,
                "test_window_days": test_days,
                "shap_sample_size": shap_sample_size,
            },
        ).__dict__
        if backend_error:
            training_summary["backend_error"] = backend_error
            model_artifacts["backend_error"] = backend_error
        return {
            "backend": backend,
            "factor_scores": factor_values,
            "factor_score": round(sum(factor_values.values()) / len(factor_values), 4) if factor_values else 0.0,
            "feature_names": feature_names,
            "model_artifacts": model_artifacts,
            "training_summary": training_summary,
            "monitoring_summary": monitoring_summary,
            "interpretation": {
                "shap_enabled": bool(shap_values),
                "top_features": [
                    {"name": name, "impact": value}
                    for name, value in self._top_feature_items(shap_values)
                ],
                "score": round(sum(factor_values.values()) / len(factor_values), 4) if factor_values else 0.0,
            },
            "traces": {
                "backend": backend,
                "train_window_days": train_days,
                "valid_window_days": valid_days,
                "test_window_days": test_days,
                "shap_sample_size": shap_sample_size,
                "backend_error": backend_error,
            },
        }

    @staticmethod
    def _top_feature_items(values: Dict[str, float]) -> List[Tuple[str, float]]:
        return sorted(values.items(), key=lambda item: abs(item[1]), reverse=True)[:3]

    @staticmethod
    def merge_backend_payloads(family_results: Sequence[_FamilyResult]) -> Dict[str, Any]:
        feature_names = sorted({name for result in family_results for name in result.feature_names})
        return {
            "feature_names": feature_names,
            "factor_scores": {result.family: result.factor_scores for result in family_results},
            "factor_score": round(sum(result.factor_score for result in family_results) / len(family_results), 4) if family_results else 0.0,
            "training_summary": {
                "algorithm": "LightGBM",
                "rolling": True,
                "backend": family_results[0].training_summary.get("backend") if family_results else "skeleton",
                "families": {result.family: result.training_summary for result in family_results},
            },
            "monitoring_summary": {
                "families": {result.family: result.monitoring_summary for result in family_results},
            },
            "model_artifacts": {
                "families": {result.family: result.model_artifacts for result in family_results},
            },
            "traces": {
                result.family: result.traces for result in family_results
            },
        }

    @staticmethod
    def _resolve_int_env(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, default))
        except Exception:
            return default

    @staticmethod
    def _resolve_float_env(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, default))
        except Exception:
            return default


__all__ = ["FactorBackendAdapter", "FactorModelArtifacts"]
