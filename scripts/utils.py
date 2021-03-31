# -*- coding: utf-8 -*-
import argparse
import logging
import spacy
import sklearn

from eznlp.token import LexiconTokenizer
from eznlp.pretrained import Vectors
from eznlp.sequence_tagging import precision_recall_f1_report
from eznlp.sequence_tagging.io import ConllIO
from eznlp.text_classification.io import TabularIO

logger = logging.getLogger(__name__)


def load_data(args: argparse.Namespace):
    if args.dataset == 'conll2003':
        conll_io = ConllIO(text_col_id=0, tag_col_id=3, scheme='BIO1', case_mode='None', number_mode='Zeros')
        train_data = conll_io.read("data/conll2003/eng.train")
        dev_data   = conll_io.read("data/conll2003/eng.testa")
        test_data  = conll_io.read("data/conll2003/eng.testb")
    elif args.dataset == 'conll2012':
        conll_io = ConllIO(text_col_id=3, tag_col_id=10, scheme='OntoNotes', line_sep_starts=["#begin", "#end", "pt/"])
        train_data = conll_io.read("data/conll2012/train.english.v4_gold_conll", encoding='utf-8')
        dev_data   = conll_io.read("data/conll2012/dev.english.v4_gold_conll", encoding='utf-8')
        test_data  = conll_io.read("data/conll2012/test.english.v4_gold_conll", encoding='utf-8')
    elif args.dataset == 'ResumeNER':
        conll_io = ConllIO(text_col_id=0, tag_col_id=1, scheme='BMES', token_sep="", pad_token="")
        train_data = conll_io.read("data/ResumeNER/train.char.bmes", encoding='utf-8')
        dev_data   = conll_io.read("data/ResumeNER/dev.char.bmes", encoding='utf-8')
        test_data  = conll_io.read("data/ResumeNER/test.char.bmes", encoding='utf-8')
    elif args.dataset == 'WeiboNER':
        conll_io = ConllIO(text_col_id=0, tag_col_id=1, scheme='BIO2', token_sep="", pad_token="", pre_text_normalizer=lambda x: x[0])
        train_data = conll_io.read("data/WeiboNER/weiboNER_2nd_conll.train", encoding='utf-8')
        dev_data   = conll_io.read("data/WeiboNER/weiboNER_2nd_conll.dev", encoding='utf-8')
        test_data  = conll_io.read("data/WeiboNER/weiboNER_2nd_conll.test", encoding='utf-8')
    elif args.dataset == 'SIGHAN2006':
        # https://github.com/v-mipeng/LexiconAugmentedNER/issues/3
        conll_io = ConllIO(text_col_id=0, tag_col_id=1, scheme='BIO2', token_sep="", pad_token="")
        train_data = conll_io.read("data/SIGHAN2006/train.txt", encoding='utf-8')
        dev_data   = conll_io.read("data/SIGHAN2006/test.txt", encoding='utf-8')
        test_data  = conll_io.read("data/SIGHAN2006/test.txt", encoding='utf-8')
        if args.command in ('finetune', 'ft'):
            for data in [train_data, dev_data, test_data]:
                for data_entry in data:
                    data_entry['tokens'] = data_entry['tokens'][:510]
    elif args.dataset == 'conll2012_zh':
        conll_io = ConllIO(text_col_id=3, tag_col_id=10, scheme='OntoNotes', line_sep_starts=["#begin", "#end", "pt/"], token_sep="", pad_token="")
        train_data = conll_io.read("data/conll2012/train.chinese.v4_gold_conll", encoding='utf-8')
        dev_data   = conll_io.read("data/conll2012/dev.chinese.v4_gold_conll", encoding='utf-8')
        test_data  = conll_io.read("data/conll2012/test.chinese.v4_gold_conll", encoding='utf-8')
        
    elif args.dataset == 'yelp2013':
        tabular_io = TabularIO(text_col_id=3, label_col_id=2, mapping={"<sssss>": "\n"}, case_mode='lower')
        train_data = tabular_io.read("data/Tang2015/yelp-2013-seg-20-20.train.ss", encoding='utf-8', sep="\t\t")
        dev_data   = tabular_io.read("data/Tang2015/yelp-2013-seg-20-20.dev.ss", encoding='utf-8', sep="\t\t")
        test_data  = tabular_io.read("data/Tang2015/yelp-2013-seg-20-20.test.ss", encoding='utf-8', sep="\t\t")
        
    elif args.dataset == 'yelp_full':
        spacy_nlp_en = spacy.load("en_core_web_sm", disable=['tagger', 'parser', 'ner'])
        tabular_io = TabularIO(text_col_id=1, label_col_id=0, mapping={"\\n": "\n", '\\"': '"'}, tokenize_callback=spacy_nlp_en, case_mode='lower')
        train_data = tabular_io.read("data/yelp_review_full/train.csv", sep=",")
        test_data  = tabular_io.read("data/yelp_review_full/test.csv", sep=",")
        
        train_data, dev_data = sklearn.model_selection.train_test_split(train_data, test_size=0.1, random_state=args.seed)
    else:
        raise Exception("Dataset does NOT exist", args.dataset)
        
    if getattr(args, 'use_softword', False) or getattr(args, 'use_softlexicon', False):
        ctb50 = Vectors.load("assets/vectors/ctb.50d.vec", encoding='utf-8')
        tokenizer = LexiconTokenizer(ctb50.itos)
        for data in [train_data, dev_data, test_data]:
            for data_entry in data:
                data_entry['tokens'].build_softwords(tokenizer.tokenize)
                data_entry['tokens'].build_softlexicons(tokenizer.tokenize)
                
                
                
    return train_data, dev_data, test_data



def evaluate_sequence_tagging(trainer, dataset):
    set_chunks_pred = trainer.predict_chunks(dataset)
    set_chunks_gold = [ex['chunks'] for ex in dataset.data]
    
    scores, ave_scores = precision_recall_f1_report(set_chunks_gold, set_chunks_pred)
    micro_f1, macro_f1 = ave_scores['micro']['f1'], ave_scores['macro']['f1']
    logger.info(f"Micro F1-score: {micro_f1*100:2.3f}%")
    logger.info(f"Macro F1-score: {macro_f1*100:2.3f}%")



def header_format(content: str, sep='=', width=100):
    side_width = max(width - len(content) - 2, 10)
    left_width = side_width // 2
    right_width = side_width - left_width
    return f"{sep*left_width} {content} {sep*right_width}"
    
