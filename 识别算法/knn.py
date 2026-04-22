import joblib
import numpy as np
import pandas as pd
import sys
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import Normalizer, StandardScaler


MODEL_PATH = "classifier.pkl"
LEGACY_MODEL_PATH = "knn.pkl"
ROBUST_MODEL_NAME = "ratio_random_forest"
ROBUSTNESS_TOLERANCE = 0.035
LEGACY_LABEL_MAP = {"PVC_RED": "PET_RED"}

class RatioFeatureBuilder(BaseEstimator, TransformerMixin):
    """把 6 通道原始强度转换成更稳定的通道比值特征。"""

    def fit(self, x, y=None):
        return self

    def transform(self, x):
        data = np.asarray(x, dtype=float)
        eps = 1e-9
        ratio_columns = []

        for i in range(data.shape[1]):
            for j in range(i + 1, data.shape[1]):
                ratio_columns.append(data[:, i] / (data[:, j] + eps))

        return np.column_stack(ratio_columns)


def normalize_label(label):
    return LEGACY_LABEL_MAP.get(str(label), str(label))


def get_prediction_label(label):
    return normalize_label(label)


class SpectrumClassifier:
    def __init__(self):
        self.model = None
        self.model_name = None
        self.cv_score = None
        self.search_results = []

    @staticmethod
    def load_data(file_path=None):
        data = pd.read_csv(file_path, header=None)
        x = data.iloc[:, :-1]
        y = data.iloc[:, -1].map(normalize_label)
        return x, y

    def _build_candidates(self):
        return [
            (
                "knn_baseline",
                Pipeline(
                    [
                        ("scaler", StandardScaler()),
                        ("normalizer", Normalizer(norm="max")),
                        ("classifier", KNeighborsClassifier()),
                    ]
                ),
                {
                    "classifier__n_neighbors": [1, 3, 5, 7],
                    "classifier__weights": ["uniform", "distance"],
                    "classifier__p": [1, 2],
                },
            ),
            (
                "ratio_random_forest",
                Pipeline(
                    [
                        ("ratio", RatioFeatureBuilder()),
                        (
                            "classifier",
                            RandomForestClassifier(
                                random_state=42,
                                n_jobs=-1,
                            ),
                        ),
                    ]
                ),
                {
                    "classifier__n_estimators": [200, 400],
                    "classifier__max_depth": [None, 5, 8],
                    "classifier__min_samples_leaf": [1, 2],
                },
            ),
            (
                "ratio_extra_trees",
                Pipeline(
                    [
                        ("ratio", RatioFeatureBuilder()),
                        (
                            "classifier",
                            ExtraTreesClassifier(
                                random_state=42,
                                n_jobs=-1,
                            ),
                        ),
                    ]
                ),
                {
                    "classifier__n_estimators": [200, 400],
                    "classifier__max_depth": [None, 5, 8],
                    "classifier__min_samples_leaf": [1, 2],
                },
            ),
        ]

    def fit(self, x_train, y_train):
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        best_search = None
        candidate_searches = {}
        self.search_results = []

        for candidate_name, estimator, param_grid in self._build_candidates():
            print(f"开始训练候选模型: {candidate_name}")
            grid_search = GridSearchCV(
                estimator=estimator,
                param_grid=param_grid,
                cv=cv,
                scoring="accuracy",
                n_jobs=-1,
            )
            grid_search.fit(x_train, y_train)

            result = {
                "name": candidate_name,
                "score": float(grid_search.best_score_),
                "params": grid_search.best_params_,
            }
            self.search_results.append(result)
            candidate_searches[candidate_name] = grid_search
            print(f"候选模型 {candidate_name} 最佳交叉验证准确率: {grid_search.best_score_:.4f}")
            print(f"候选模型 {candidate_name} 最佳参数: {grid_search.best_params_}")

            if best_search is None or grid_search.best_score_ > best_search.best_score_:
                best_search = grid_search
                self.model_name = candidate_name

        selected_search = best_search
        robust_search = candidate_searches.get(ROBUST_MODEL_NAME)
        if (
            robust_search is not None
            and best_search.best_score_ - robust_search.best_score_ <= ROBUSTNESS_TOLERANCE
        ):
            selected_search = robust_search
            self.model_name = ROBUST_MODEL_NAME
            print(
                "检测到比值特征树模型与最高交叉验证分数接近，"
                "为提升部署时对光强波动的鲁棒性，默认切换到 ratio_random_forest。"
            )

        self.model = selected_search.best_estimator_
        self.cv_score = float(selected_search.best_score_)
        print(f"最终部署模型: {self.model_name}")
        print(f"最终部署模型交叉验证准确率: {self.cv_score:.4f}")

    def predict(self, x_test):
        return self.model.predict(x_test)

    @staticmethod
    def evaluate(y_test, y_pred):
        return accuracy_score(y_test, y_pred)

    def save(self, path):
        joblib.dump(self, path)

    @staticmethod
    def load(path):
        return joblib.load(path)

    @classmethod
    def load_best_available(cls, paths=None):
        candidate_paths = paths or (MODEL_PATH, LEGACY_MODEL_PATH)
        last_error = None

        for path in candidate_paths:
            try:
                return cls.load(path)
            except FileNotFoundError as exc:
                last_error = exc

        raise last_error if last_error else FileNotFoundError("未找到可用模型文件。")


# 保留旧类名，避免 UI 或旧脚本直接引用 KNN 时失效
RatioFeatureBuilder.__module__ = "knn"
SpectrumClassifier.__module__ = "knn"
KNN = SpectrumClassifier
KNN.__module__ = "knn"

if __name__ == "__main__":
    sys.modules.setdefault("knn", sys.modules[__name__])


def main():
    classifier = SpectrumClassifier()
    train_path = "data/train_data.csv"
    test_path = "data/test_data.csv"
    x_train, y_train = classifier.load_data(train_path)
    x_test, y_test = classifier.load_data(test_path)

    classifier.fit(x_train, y_train)

    y_pred = classifier.predict(x_test)
    print("测试集准确率:", classifier.evaluate(y_test, y_pred))

    results_df = pd.DataFrame({"y_test": y_test, "y_pred": y_pred})
    results_df["Correct"] = results_df["y_test"] == results_df["y_pred"]

    print("\n预测结果详情:")
    print(results_df.to_string())

    classifier.save(MODEL_PATH)
    classifier.save(LEGACY_MODEL_PATH)
    print(f"\n模型已保存到: {MODEL_PATH}")
    print(f"兼容副本已保存到: {LEGACY_MODEL_PATH}")


if __name__ == "__main__":
    main()
