#!/usr/local/bin/python3

import ROOT
from bdt_common import variables, spectators, fill_histos, manual, bdt


f_input = ROOT.TFile("mc_file.root")
t = ROOT.TTree()
t = f_input.Get("mc_tree")

ROOT.TMVA.Tools.Instance()
fout = ROOT.TFile("test.root", "RECREATE")
factory = ROOT.TMVA.Factory("TMVAClassification", fout,
                            ":".join([
                                "!V",
                                "!Silent",
                                "Color",
                                "DrawProgressBar",
                                "Transformations=I;D;P;G,D",
                                "AnalysisType=Classification"]))
dataloader = ROOT.TMVA.DataLoader("dataset")

for name, var in variables:
    dataloader.AddVariable(name, "F")

for name, var in spectators:
    dataloader.AddSpectator(name, "F")

sigCut = ROOT.TCut("is_signal > 0.5")
bgCut = ROOT.TCut("is_signal <= 0.5")

dataloader.AddSignalTree(t)
dataloader.AddBackgroundTree(t)
dataloader.PrepareTrainingAndTestTree(sigCut, bgCut,
                                      "SplitMode=Alternate:NormMode=NumEvents:!V")

method = factory.BookMethod(dataloader, ROOT.TMVA.Types.kBDT, "BDT",
                            ":".join([
                                "!H:!V:NTrees=50",
                                "MinNodeSize=2.5%",
                                "MaxDepth=3",
                                "BoostType=AdaBoost",
                                "AdaBoostBeta=0.5",
                                "UseBaggedBoost",
                                "BaggedSampleFraction=0.5",
                                "SeparationType=GiniIndex",
                                "nCuts=20"]))

factory.TrainAllMethods()
factory.TestAllMethods()
factory.EvaluateAllMethods()

fill_histos("cosmic_mc", bdt, manual)
fill_histos("bnb", bdt, manual)
fill_histos("bnbext", bdt, manual)
