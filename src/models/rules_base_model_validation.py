import re
import yaml
from dataclasses import dataclass
from loguru import logger
import pandas as pd
from fuzzywuzzy import fuzz
from tqdm import tqdm

logger.info("Init rules_base_model")


@dataclass
class RuleBasedClassifier:
    def __init__(self):
        """
        A class representing a rule-based spam classifier. The class contains methods for training and testing the model, as well as
        classifying new messages based on a set of pre-defined rules.

        """

        with open("config.yml", "r") as f:
            config = yaml.safe_load(f)
            self.path_stop_words = config["stop_words"]
            self.path_dangerous_words = config["dangerous_words"]
            self.path_spam_words = config["spam_words"]
            self.path_words_fuzzy_not_enough = config["words_fuzzy_not_enough"]

        self.stop_words = pd.read_csv(self.path_stop_words, sep=";")[
            "stop_words"
        ].tolist()
        self.dangerous_words = pd.read_csv(self.path_dangerous_words, sep=";")[
            "dangerous_words"
        ].tolist()
        self.spam_words = pd.read_csv(self.path_spam_words, sep=";")[
            "spam_words"
        ].tolist()
        self.words_fuzzy_not_enough = pd.read_csv(
            self.path_words_fuzzy_not_enough, sep=";"
        )["words_fuzzy_not_enough"].tolist()
        self.not_spam_id = []

        self.rules = [
            {"name": "contains_link", "check": self._check_contains_link},
            {"name": "contains_stop_word", "check": self._check_contains_stop_word},
            {
                "name": "contains_dangerous_words",
                "check": self._check_contains_dangerous_words,
            },
            {"name": "contains_spam_words", "check": self._check_contains_spam_words},
            {"name": "contains_photo", "check": self._check_contains_photo},
            {"name": "contains_not_spam_id", "check": self._check_not_spam_id},
            {
                "name": "contains_special_characters",
                "check": self._check_special_characters,
            },
            {"name": "check_len_message", "check": self._check_len_message},
            {
                "name": "contains_words_fuzzy_not_enough",
                "check": self._check_words_fuzzy_not_enough,
            },
            {
                "name": "contains_сapital_letters",
                "check": self._check_capital_letters,
            },
        ]

    def fit(self, X, y):
        """
        Fits the model to the training data.

        Parameters:
            X: The input features of shape (n_samples, n_features).
            y: The target labels of shape (n_samples,).

        Returns:
            None
        """
        mask_not_spam = y == 0
        self.not_spam_id = X[mask_not_spam]["from_id"].unique()
        return None

    def predict(self, X):
        """
        Predicts the scores for the given input using the trained model.

        Parameters:
            X (pandas DataFrame): The input data to predict scores for.

        Returns:
            numpy array: An array of predicted scores for the input data.
        """
        logger.info("Predicting...")
        pred_scores = []
        name_features = ''
        for index in tqdm(range(len(X))):
            message = X.iloc[index, :]
            score, temp_name_features = self._predict_message(message)
            name_features += temp_name_features
            pred_scores.append(score)
        return pred_scores, name_features

    def _predict_message(self, message):
        """
        Calculate the total score for a given message by applying a set of rules.

        Parameters:
            message (any): The message to be evaluated.

        Returns:
            float: The total score of the message based on the rules.
        """
        total_score = 0.0
        name_features = ''
        for rule in self.rules:
            temp_score, temp_name_features = rule["check"](message)
            total_score += temp_score
            name_features += temp_name_features
        total_score_normalized = self._normalize_score(total_score, threshold=1)
        return total_score_normalized, name_features
    
    def _normalize_score(self, score, threshold):
        """
        Normalize the score to a range from 0 to 1 using a threshold value.

        Parameters:
            score (float): The input score.
            threshold (float): The threshold value above which the score is considered maximum (1).

        Returns:
            float: The normalized score.
        """
        if score >= threshold:
            normalized_score = 1.0
        elif score < 0:
            normalized_score = 0
        else:
            normalized_score = score / threshold
        return normalized_score

    def _check_contains_link(self, message):
        score = 0.0
        feature = ''

        # Regular expression pattern to match URLs
        url_pattern = r"(?i)\b((?:http[s]?://|www\d{0,3}[.]|telegram[.]me/|t[.]me/|telegra[.]ph/)[^\s()<>]+(?:\([\w\d]+\)|([^[:punct:]\s]|/)))"

        # Search for URLs in the message text
        urls = re.findall(url_pattern, message["text"])
        
        # Check if any found urls are internal Telegram links
        internal_links = [url for url in urls if 't.me' in url[0] or 'telegra.ph/' in url[0]]
        
        if internal_links or 'none' in message["text"].lower().split()[-1]:
            score += 0.15
            feature = "[+0.15] - В сообщении содержится telegram ссылка\n"

        return score, feature


    def _check_contains_stop_word(self, message):
        """
        Checks if the message contains any stop words and calculates a score based on the number of stop words found.

        Parameters:
            message (dict): The message containing the text to be checked.

        Returns:
            float: The score representing the presence of stop words in the message.
        """

        score = 0.0
        feature = ''
        for words in self.stop_words:
            if fuzz.token_set_ratio(words.lower(), message["text"].lower()) >= 77:
                score += 0.30
                feature += f'[+0.3] - В сообщении содержится: "{words}"\n'
        return score, feature

    def _check_contains_dangerous_words(self, message):
        """
        Checks if the given message contains any dangerous words and calculates a score based on the number of occurrences.

        Parameters:
            message (dict): The message to check for dangerous words.

        Returns:
            float: The score calculated based on the number of dangerous words found.
        """
        score = 0.0
        feature = ''
        for words in self.dangerous_words:
            if fuzz.token_set_ratio(words.lower(), message["text"].lower()) >= 77:
                score += 0.15
                feature += f'[+0.15] - В сообщении содержится: "{words}"\n'
        return score, feature

    def _check_contains_spam_words(self, message):
        """
        Checks if the given message contains the phrase "читать продолжение" and returns a score based on the result.

        Parameters:
            message (dict): The message to check.

        Returns:
            float: The score, which is incremented by 1.0 if the phrase is found.
        """
        score = 0.0
        feature = ''
        for words in self.spam_words:
            if fuzz.token_set_ratio(words.lower(), message["text"].lower()) >= 77:
                score += 0.5
                feature += f'[+0.5] - В сообщении содержится: "{words}"\n'
        return score, feature

    def _check_contains_photo(self, message):
        """
        Checks if the given message contains a photo and returns a score based on the result.

        Parameters:
            message (dict): The message to check.

        Returns:
            float: The score based on whether the message contains a photo.
        """
        score = 0.0
        feature = ''
        if message["photo"]:
            score += 0.15
            feature = '[+0.15] - В сообщении содержится фотография\n'
        return score, feature

    def _check_not_spam_id(self, message):
        """
        Checks if the given message is not spam based on the `from_id` field.

        Parameters:
            message (dict): The message to check.

        Returns:
            float: The spam score of the message. If the `from_id` is in the `not_spam_id` list, the score is decreased by 1.0.
        """
        score = 0.0
        feature = ''
        if message["from_id"] in self.not_spam_id:
            score -= 0.5
            feature = '[-0.5] - Пользователь ранее не писал спам\n'
        return score, feature

    def _check_special_characters(self, message):
        """
        Check if the given message contains any special characters and calculate a score based on the presence of such characters.

        Parameters:
            message (str): The message to check for special characters.

        Returns:
            float: The calculated score based on the presence of special characters.
        """
        score = 0.0
        pattern = "[à-üÀ-Üα-ωΑ-ΩҐЄЇІґєїі&&[^ё̰]]"
        pattern += "|[Α-Ωα-ω̰]"
        feature = ''
        result = re.findall(pattern, message["text"].lower())
        if result:
            score += len(result) * 0.1
            feature = f'[+{round(len(result) * 0.1, 1)}] - Греческие/Украинские буквы в сообщении ({", ".join(result[:3])})\n'
        return score, feature

    def _check_len_message(self, message):
        """
        Calculate the score for the length of the message.

        Parameters:
            message (dict): A dictionary containing the message text.

        Returns:
            float: The score for the length of the message.
        """
        score = 0.0
        feature = ''
        if len(message["text"]) < 5 and len(message['text']) != 0:
            score += 0.1
            feature = '[+0.1] - Сообщение чересчур короткое'
        return score, feature

    def _check_words_fuzzy_not_enough(self, message):
        """
        Calculate the score for a given message based on the presence of words in the 'words_fuzzy_not_enough' list.

        Parameters:
            message (dict): A dictionary containing the message text.

        Returns:
            float: The calculated score based on the presence of words from 'words_fuzzy_not_enough' list in the message text.
        """
        score = 0.0
        feature = ''
        for word_fuzzy_not_enough in self.words_fuzzy_not_enough:
            for word in message["text"].split():
                if word_fuzzy_not_enough == re.sub(r"[^a-zа-я]", "", word.lower()):
                    score += 0.3
        return score, feature

    def _check_capital_letters(self, message):
        """
        Calculates the score based on the presence of capital letters in the input message.

        Parameters:
            message (dict): The input message containing the text.

        Returns:
            float: The calculated score.

        """
        score = 0.0

        capital_pattern = "[A-ZА-Я]"
        pattern = "[a-zA-Zа-яА-Я]"

        capital_letters = re.findall(capital_pattern, message["text"])
        letters = re.findall(pattern, message["text"])
        feature = ''
        try:
            if len(capital_letters) / len(letters) > 0.4 and len(message["text"]) > 5:
                score += 0.15
                feature = '[+0.15] - Большая концентрация заглавных букв'
        except ZeroDivisionError:
            pass
        return score, feature
