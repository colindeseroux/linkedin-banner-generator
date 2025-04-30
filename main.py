##### Standard #####
import argparse
import csv
import json
import re

##### Third parties #####
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_gradient_magnitude
from wordcloud import WordCloud, ImageColorGenerator


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    :return: Parsed arguments.
    :rtype: Namespace
    """
        
    parser = argparse.ArgumentParser(description="Generate a LinkedIn banner with a word cloud. See https://github.com/amueller/word_cloud for more details.")
    parser.add_argument(
        "text",
        type=str,
        help="text to generate in the word cloud (allowed files: .txt, .csv, .json or string separated by commas)"
    )
    parser.add_argument(
        "--font-path",
        type=str,
        default=None,
        help="path to the font file [default: None]"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1584,
        help="width of the banner [default: 1584]"
    )
    parser.add_argument(
        "--height",
        type=int,
        default=396,
        help="height of the banner [default: 396]"
    )
    parser.add_argument(
        "--prefer-horizontal",
        type=float,
        default=0.9,
        help="percentage of words to be horizontal [default: 0.9]"
    )
    parser.add_argument(
        "--contour-width",
        type=int,
        default=0,
        help="width of the contour [default: 0]"
    )
    parser.add_argument(
        "--contour-color",
        type=str,
        default="black",
        help="color of the contour [default: black]"
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="scale of the word cloud [default: 1.0]"
    )
    parser.add_argument(
        "--min-font-size",
        type=int,
        default=10,
        help="minimum font size [default: 10]"
    )
    parser.add_argument(
        "--font-step",
        type=int,
        default=1,
        help="font step [default: 1]"
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=2000,
        help="maximum number of words [default: 2000]"
    )
    parser.add_argument(
        "--stopwords",
        type=str,
        default=None,
        help="path to the stopwords file [default: None]"
    )
    parser.add_argument(
        "--background-color",
        type=str,
        default="white",
        help="background color [default: white]"
    )
    parser.add_argument(
        "--max-font-size",

        type=int,
        default=100,
        help="maximum font size [default: 100]"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="RGB",
        help="mode of the word cloud [default: RGB]"
    )
    parser.add_argument(
        "--relative-scaling",
        type=float,
        default=0.5,
        help="relative scaling of the words [default: 0.5]"
    )
    parser.add_argument(
        "--colormap",
        type=str,
        default="viridis",
        help="colormap of the word cloud [default: viridis]"
    )
    parser.add_argument(
        "--repeat",
        action="store_true",
        help="repeat the words [default: False]"
    )
    parser.add_argument(
        "--include-numbers",
        action="store_true",
        help="include numbers in the word cloud [default: False]"
    )
    parser.add_argument(
        "--mask",
        type=str,
        default=None,
        help="path to the mask image [default: None]"
    )
    parser.add_argument(
        "--color-mask",
        action="store_true",
        help="use the mask image as a color mask background black and your color (!white) [default: False]"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="linkedin_banner.jpg",
        help="path to save the generated banner [default: linkedin_banner.jpg]"
    )
        
    return parser.parse_args()


def word_weight_to_dict(entries: str) -> dict:
    """
    Convert a string of words and weights to a dictionary.

    :param entries: Words and weights in the format "word weight" or just "word" (weight defaults to 1).
    :type entries: str
        
    :return: Dictionary with words as keys and weights as values.
    :rtype: dict
    """
        
    frequencies = {}
    
    for entry in entries:
        parts = entry.strip().split()
        parts_len = len(parts)
        
        if parts_len > 1:
            word, weight = parts, parts[parts_len - 1]
            word = " ".join(word[:-1])
            
            try:
                frequencies[word] = int(weight)
            except ValueError:
                frequencies[entry.strip()] = 1
        elif entry.strip():
            frequencies[entry.strip()] = 1

    return frequencies


def load_csv(path: str) -> dict:
    """
    Load words and their weights from a CSV file.
    
    Expected format:
    - "word,weight" or with headers "word,weight" (weight,word if you want with headers)
    - "word;weight" or with headers "word;weight" (weight;word if you want with headers)
    
    :param path: Path to the CSV file.
    :type path: str
    
    :return: Dictionary with words as keys and weights as values.
    :rtype: dict
    """
    
    with open(path, "r", newline="", encoding="utf-8") as csvfile:
        sample = csvfile.read(1024)
        csvfile.seek(0)
        dialect = csv.Sniffer().sniff(sample)
        has_header = csv.Sniffer().has_header(sample)
        delimiter = dialect.delimiter

    with open(path, "r", encoding="utf-8") as file:
        reader = csv.reader(file, delimiter=delimiter)
        rows = list(reader)

    if has_header:
        header = [h.lower() for h in rows[0]]
        rows = rows[1:]
    else:
        header = None

    word_weights = {}

    for row in rows:
        try:
            if header:
                if "word" in header and "weight" in header:
                    word = row[header.index("word")].strip()
                    weight = int(row[header.index("weight")])
                else:
                    word, weight = row[0].strip(), int(row[1])
            else:
                if re.match(r"^[\d.]+$", row[0]):
                    weight, word = int(row[0]), row[1].strip()
                else:
                    word, weight = row[0].strip(), int(row[1])
        except (ValueError, IndexError):
            word = row[0].strip()
            weight = 1

        word_weights[word] = weight

    return word_weights


def load_json(path: str) -> dict:
    """
    Load words and their weights from a JSON file.

    Expected format:
    - {"word": "weight", "word": "weight"}
    - {"words": [word1, word2], "weights": [weight1, weight2]}
    - [{"word": "weight"}, {"word": "weight"}]

    :param path: Path to the JSON file.
    :type path: str

    :return: Dictionary with words as keys and weights as values.
    :rtype: dict
    """
    
    with open(path, "r") as file:
        content = json.load(file)

    if isinstance(content, dict):
        if "words" in content and "weights" in content:
            return dict(zip(content["words"], content["weights"]))
        
        return content

    if isinstance(content, list):
        frequencies = {}
        
        for item in content:
            if isinstance(item, dict) and "word" in item and "weight" in item:
                frequencies[item["word"]] = item["weight"]
                
        return frequencies

    return {}


def load_txt(path: str) -> str:
    """
    Load words and their weights from a text file.
    
    Expected format:
    - "word,word" or "word weight,word weight" (comma-separated, no spaces between commas and words)
    - "word\\nword" or "word weight\\nword weight" (newline-separated)
    
    :param path: Path to the text file.
    :type path: str
    
    :return: Dictionary with words as keys and weights as values.
    :rtype: dict
    """
    
    with open(path, "r") as file:
        content = file.read().strip()
    
    if re.search(r"(?<=\S),(?=\S)", content):
        entries = re.split(r"(?<=\S),(?=\S)", content)
    else:
        entries = content.split("\n")

    return word_weight_to_dict(entries)


def load_pure_text(text: str) -> str:
    """
    Load words and their weights from a string.
    
    Expected format:
    - "word,word" or "word weight,word weight" (comma-separated, no spaces between commas and words)
    
    :param text: Text to analyze.
    :type text: str
    
    :return: Dictionary with words as keys and weights as values.
    :rtype: dict
    """
    
    entries = re.split(r"(?<=\S),(?=\S)", text)
    
    return word_weight_to_dict(entries)


def get_word_frequencies(string: str) -> dict:
    """
    Get word frequencies from the text.

    :param string: Text or path to analyze.
    :type string: str
        
    :return: Dictionary with words as keys and frequencies as values.
    :rtype: dict
    """
    
    if string.endswith(".csv"):
        return load_csv(string)
    
    if string.endswith(".json"):
        return load_json(string)
    
    if string.endswith(".txt"):
        return load_txt(string)
    
    return load_pure_text(string)


def load_mask(mask: str, color_mask: bool) -> tuple:
    """
    Load the mask image.

    :param mask: Path to the mask image.
    :type mask: str
    :param color_mask: Whether to use the mask image as a color mask.
    :type color_mask: bool
        
    :return: Tuple of the mask image and the mask mask.
    :rtype: tuple
    """
    
    mask_color = np.array(Image.open(mask))
    
    if not color_mask:
        return None, mask_color
    
    mask_mask = mask_color.copy()
    mask_mask[mask_color.sum(axis=2) == 0] = 255
    
    edges = np.mean([gaussian_gradient_magnitude(mask_color[:, :, i] / 255., 2) for i in range(3)], axis=0)
    mask_mask[edges > .08] = 255
    
    return mask_color, mask_mask


def generate_wordcloud(frequencies: str, args: argparse.Namespace, mask: np.array = None) -> WordCloud:
    """
    Generate a word cloud from the given text.

    :param frequencies: Dictionary with words as keys and frequencies as values.
    :type frequencies: dict
    :param args: Command line arguments.
    :type args: Namespace
    :param mask: Path to the mask image.
    :type mask: str
    
    :return: Generated word cloud.
    :rtype: WordCloud
    """
        
    wordcloud = WordCloud(
        font_path=args.font_path,
        width=args.width,
        height=args.height,
        prefer_horizontal=args.prefer_horizontal,
        mask=mask,
        contour_width=args.contour_width,
        contour_color=args.contour_color,
        scale=args.scale,
        min_font_size=args.min_font_size,
        font_step=args.font_step,
        max_words=args.max_words,
        stopwords=args.stopwords,
        background_color=args.background_color,
        max_font_size=args.max_font_size,
        mode=args.mode,
        relative_scaling=args.relative_scaling,
        colormap=args.colormap,
        repeat=args.repeat,
        include_numbers=args.include_numbers,
    ).generate_from_frequencies(frequencies)
       
    return wordcloud


def run():
    """
    Run the app.
    """
    
    args = parse_args()
        
    frequences = get_word_frequencies(args.text)
    
    mask_color, mask_mask = load_mask(args.mask, args.color_mask) if args.mask else (None, None)
    
    wordcloud = generate_wordcloud(frequences, args, mask_mask)
    
    if args.color_mask:
        image_colors = ImageColorGenerator(mask_color)
        wordcloud.recolor(color_func=image_colors)
        
    wordcloud.to_file(args.output)
    
    print(f"Banner saved to {args.output}")
    
    return args.output
    

if __name__ == "__main__":
    run()