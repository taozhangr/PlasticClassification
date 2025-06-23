import joblib
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GridSearchCV
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler, Normalizer


class KNN:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.normalizer = Normalizer(norm='max')

    @staticmethod
    def load_data(file_path=None):
        # 读取数据
        data = pd.read_csv(file_path, header=None)
        x = data.iloc[:, :-1]
        y = data.iloc[:, -1]
        return x, y

    def fit(self, x_train, y_train):
        # 定义参数网格
        param_grid = {
            'n_neighbors': range(1,6),
            'weights': ['uniform', 'distance'],
            'p': [1, 2],
        }

        # 先标准化，后归一化
        x_train_processed = self.scaler.fit_transform(x_train)
        x_train_processed = self.normalizer.transform(x_train_processed)

        # GridSearchCV的迭代器
        grid_search = GridSearchCV(KNeighborsClassifier(n_jobs=-1), param_grid, cv=5, scoring='accuracy', verbose=1)

        print("开始网格搜索优化超参数...")

        grid_search.fit(x_train_processed, y_train)

        print(f"最佳参数: {grid_search.best_params_}")
        print(f"最佳交叉验证准确率: {grid_search.best_score_:.4f}")

        # 使用最佳参数重新训练模型
        self.model = grid_search.best_estimator_

    def predict(self, x_test):
        # 先标准化，后归一化
        x_test = self.scaler.transform(x_test)
        x_test = self.normalizer.transform(x_test)
        return self.model.predict(x_test)

    @staticmethod
    def evaluate(y_test, y_pred):
        return accuracy_score(y_test, y_pred)

    # 可选：保存/加载模型
    def save(self, path):
        joblib.dump(self, path)

    @staticmethod
    def load(path):
        return joblib.load(path)


def main():
    knn = KNN()
    train_path = 'data/train_data.csv'
    test_path = 'data/test_data.csv'
    x_train, y_train = knn.load_data(train_path)
    x_test, y_test = knn.load_data(test_path)

    knn.fit(x_train, y_train)

    y_pred = knn.predict(x_test)
    print("准确率:", knn.evaluate(y_test, y_pred))

    # 创建一个DataFrame来展示结果
    results_df = pd.DataFrame({'y_test': y_test, 'y_pred': y_pred})
    results_df['Correct'] = results_df['y_test'] == results_df['y_pred']

    print("\n预测结果详情:")
    print(results_df.to_string())

    # 保存模型
    knn.save('knn.pkl')


if __name__ == '__main__':
    main()