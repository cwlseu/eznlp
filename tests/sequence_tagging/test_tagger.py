# -*- coding: utf-8 -*-
import pytest
import torch

from eznlp.token import Token, LexiconTokenizer
from eznlp.config import ConfigDict
from eznlp.model import OneHotConfig, MultiHotConfig, EncoderConfig
from eznlp.model import NestedOneHotConfig, CharConfig, SoftLexiconConfig
from eznlp.pretrained import ELMoConfig, BertLikeConfig, FlairConfig
from eznlp.sequence_tagging import SequenceTaggingDecoderConfig, SequenceTaggerConfig
from eznlp.sequence_tagging import SequenceTaggingDataset
from eznlp.sequence_tagging import SequenceTaggingTrainer


class TestTagger(object):
    def _assert_batch_consistency(self):
        self.model.eval()
        
        batch012 = self.dataset.collate([self.dataset[i] for i in range(0, 3)]).to(self.device)
        batch123 = self.dataset.collate([self.dataset[i] for i in range(1, 4)]).to(self.device)
        losses012, hidden012 = self.model(batch012, return_hidden=True)
        losses123, hidden123 = self.model(batch123, return_hidden=True)
        
        min_step = min(hidden012.size(1), hidden123.size(1))
        delta_hidden = hidden012[1:, :min_step] - hidden123[:-1, :min_step]
        assert delta_hidden.abs().max().item() < 1e-4
        
        delta_losses = losses012[1:] - losses123[:-1]
        assert delta_losses.abs().max().item() < 2e-4
        
        pred012 = self.model.decode(batch012)
        pred123 = self.model.decode(batch123)
        assert pred012[1:] == pred123[:-1]
        
        
    def _assert_trainable(self):
        optimizer = torch.optim.AdamW(self.model.parameters())
        trainer = SequenceTaggingTrainer(self.model, optimizer=optimizer, device=self.device)
        dataloader = torch.utils.data.DataLoader(self.dataset, 
                                                 batch_size=4, 
                                                 shuffle=True, 
                                                 collate_fn=self.dataset.collate)
        trainer.train_epoch(dataloader)
        
        
    def _setup_case(self, data, device):
        self.device = device
        
        self.dataset = SequenceTaggingDataset(data, self.config)
        self.dataset.build_vocabs_and_dims()
        self.model = self.config.instantiate().to(self.device)
        
        
    @pytest.mark.parametrize("enc_arch", ['Conv', 'Gehring', 'LSTM', 'GRU', 'Transformer'])
    @pytest.mark.parametrize("shortcut", [False, True])
    @pytest.mark.parametrize("dec_arch", ['softmax', 'CRF'])
    def test_tagger(self, enc_arch, shortcut, dec_arch, conll2003_demo, device):
        self.config = SequenceTaggerConfig(intermediate2=EncoderConfig(arch=enc_arch, shortcut=shortcut), 
                                           decoder=SequenceTaggingDecoderConfig(arch=dec_arch))
        self._setup_case(conll2003_demo, device)
        self._assert_batch_consistency()
        self._assert_trainable()
        
    @pytest.mark.parametrize("arch", ['Conv', 'LSTM'])
    def test_tagger_with_char(self, arch, conll2003_demo, device):
        char_config = CharConfig(encoder=EncoderConfig(arch=arch, 
                                                       hid_dim=128, 
                                                       num_layers=1, 
                                                       in_drop_rates=(0.5, 0.0, 0.0)))
        self.config = SequenceTaggerConfig(nested_ohots=ConfigDict({'char': char_config}))
        self._setup_case(conll2003_demo, device)
        self._assert_batch_consistency()
        self._assert_trainable()
        
        
    def test_tagger_with_softlexicon(self, ctb50, ResumeNER_demo, device):
        tokenizer = LexiconTokenizer(ctb50.itos)
        for data_entry in ResumeNER_demo:
            data_entry['tokens'].build_softlexicons(tokenizer.tokenize)
        
        self.config = SequenceTaggerConfig(nested_ohots=ConfigDict({'softlexicon': SoftLexiconConfig(vectors=ctb50)}))
        self._setup_case(ResumeNER_demo, device)
        self._assert_batch_consistency()
        self._assert_trainable()
        
        
    def test_tagger_with_intermediate(self, conll2003_demo, device):
        self.config = SequenceTaggerConfig(intermediate1=EncoderConfig(), 
                                           intermediate2=EncoderConfig())
        self._setup_case(conll2003_demo, device)
        self._assert_batch_consistency()
        self._assert_trainable()
        
    def test_tagger_with_more_fields(self, conll2003_demo, device):
        self.config = SequenceTaggerConfig(ohots=ConfigDict({f: OneHotConfig(field=f, emb_dim=20) for f in Token._basic_ohot_fields}), 
                                           mhots=ConfigDict({f: MultiHotConfig(field=f, emb_dim=20) for f in Token._basic_mhot_fields}))
        self._setup_case(conll2003_demo, device)
        self._assert_batch_consistency()
        self._assert_trainable()
        
    @pytest.mark.parametrize("scheme", ['BIO1', 'BIO2'])
    def test_tagger_with_alternative_schemes(self, scheme, conll2003_demo, device):
        self.config = SequenceTaggerConfig(decoder=SequenceTaggingDecoderConfig(scheme=scheme))
        self._setup_case(conll2003_demo, device)
        self._assert_batch_consistency()
        self._assert_trainable()
        
        
    @pytest.mark.parametrize("freeze", [False, True])
    def test_tagger_with_pretrained_vector(self, freeze, glove100, conll2003_demo, device):
        self.config = SequenceTaggerConfig(ohots=ConfigDict({'text': OneHotConfig(field='text', vectors=glove100, freeze=freeze)}))
        self._setup_case(conll2003_demo, device)
        self._assert_batch_consistency()
        self._assert_trainable()
        
    @pytest.mark.parametrize("freeze", [False, True])
    def test_tagger_with_elmo(self, freeze, elmo, conll2003_demo, device):
        self.config = SequenceTaggerConfig(ohots=None, 
                                           elmo=ELMoConfig(elmo=elmo))
        self._setup_case(conll2003_demo, device)
        self._assert_batch_consistency()
        self._assert_trainable()
        
    @pytest.mark.parametrize("freeze", [False, True])
    def test_tagger_with_bert_like(self, freeze, bert_like_with_tokenizer, conll2003_demo, device):
        bert_like, tokenizer = bert_like_with_tokenizer
        self.config = SequenceTaggerConfig(ohots=None, 
                                           bert_like=BertLikeConfig(bert_like=bert_like, tokenizer=tokenizer, freeze=freeze))
        self._setup_case(conll2003_demo, device)
        self._assert_batch_consistency()
        self._assert_trainable()
        
    @pytest.mark.parametrize("freeze", [False, True])
    def test_tagger_with_flair(self, freeze, flair_fw_lm, flair_bw_lm, conll2003_demo, device):
        self.config = SequenceTaggerConfig(ohots=None, 
                                           flair_fw=FlairConfig(flair_lm=flair_fw_lm, freeze=freeze),  
                                           flair_bw=FlairConfig(flair_lm=flair_bw_lm, freeze=freeze))
        self._setup_case(conll2003_demo, device)
        self._assert_batch_consistency()
        self._assert_trainable()
        
        
    @pytest.mark.parametrize("use_amp", [False, True])
    def test_tagger_train_steps(self, use_amp, conll2003_demo, device):
        if use_amp and device.type.startswith('cpu'):
            pytest.skip("test requires cuda, while current session runs on cpu")
        
        self.config = SequenceTaggerConfig()
        self._setup_case(conll2003_demo, device)
        
        optimizer = torch.optim.AdamW(self.model.parameters())
        trainer = SequenceTaggingTrainer(self.model, optimizer=optimizer, use_amp=use_amp, device=self.device)
        dataloader = torch.utils.data.DataLoader(self.dataset, 
                                                 batch_size=4, 
                                                 shuffle=True, 
                                                 collate_fn=self.dataset.collate)
        trainer.train_steps(train_loader=dataloader, 
                            dev_loader=dataloader, 
                            num_epochs=4, 
                            disp_every_steps=1, 
                            eval_every_steps=2)
        
        