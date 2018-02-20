#!/usr/local/bin/python3

import ROOT
import statistics
import math
from array import array
from glob import glob
from root_numpy import hist2array
import numpy as np
from bdt_common import x_start, x_end, y_start, y_end, z_start, z_end, bins
import pickle
from proton_energy import length2energy

def choose_plane(root_chain):
    total_hits = [0, 0, 0]
    shower_hits = [0, 0, 0]
    track_hits = [0, 0, 0]

    for i_sh in range(root_chain.n_showers):
        for i_plane in range(len(root_chain.shower_nhits[i_sh])):
            total_hits[i_plane] += root_chain.shower_nhits[i_sh][i_plane]
            shower_hits[i_plane] += root_chain.shower_nhits[i_sh][i_plane]

    for i_tr in range(root_chain.n_tracks):
        for i_plane in range(len(root_chain.track_nhits[i_tr])):
            total_hits[i_plane] += root_chain.track_nhits[i_tr][i_plane]
            track_hits[i_plane] += root_chain.track_nhits[i_tr][i_plane]

    product = [t * s for t, s in zip(track_hits, shower_hits)]

    return product.index(max(product))

def is_fiducial(point):
    ok_y = y_start + 20 < point[1] < y_end - 20
    ok_x = x_start + 10 < point[0] < x_end - 10
    ok_z = z_start + 10 < point[2] < z_end - 50
    return ok_y and ok_x and ok_z


def is_active(point):
    ok_y = y_start < point[1] < y_end
    ok_x = x_start < point[0] < x_end
    ok_z = z_start < point[2] < z_end
    return ok_y and ok_x and ok_z


def gauss_exp(var, par):
    """
    n:par[0]
    mu:par[1]
    sigma:par[2]
    k:par[3]
    """
    n = par[0]
    mu = par[1]
    sigma = par[2]
    k = par[3]
    x = var[0]

    if (x - mu) / sigma >= -k:
        return n * math.exp(-0.5 * ((x - mu) / sigma)**2)
    else:
        return n * math.exp(k**2 / 2 + k * ((x - mu) / sigma))


ROOT.gStyle.SetPaintTextFormat(".2f")
ROOT.gStyle.SetNumberContours(999)
ROOT.gStyle.SetOptStat(0)
ROOT.gStyle.SetOptFit(0)
ROOT.gStyle.SetPalette(ROOT.kBird)
nue_cosmic = glob("mc_nue_1e0p/*.root")
chain = ROOT.TChain("robertoana/pandoratree")

for f in nue_cosmic:
    chain.Add(f)

entries = chain.GetEntries()

total = 0
splitted_event = 0
incomplete_event = 0
perfect_event = 0
wrong_event = 0
track_ok_shower_mis = 0
track_ok_shower_no = 0
shower_ok_track_mis = 0
shower_ok_track_no = 0
track_no_shower_no = 0
flash_not_passed = 0


h_matrix = ROOT.TH2F("h_matrix",
                          ";E_{k}^{reco} [GeV];E_{#nu} [GeV]",
                          len(bins) - 1, bins, len(bins) - 1, bins)

h_e_true_reco = ROOT.TH2F("h_e_true_reco", ";E_{k}^{true} [GeV];E_{k}^{reco} [GeV]",
                          50, 0, 2, 50, 0, 2)

h_e_true = ROOT.TH1F("h_e_true", "", len(bins) - 1, bins)
h_e_reco = ROOT.TH1F("h_e_reco", "", len(bins) - 1, bins)

h_e_res = ROOT.TH1F("h_res",
                    ";(E_{k}^{corr} - E_{k}^{true}) / E_{k}^{true};N. Entries / 0.04",
                    50, -1, 1)

h_e_nu_kin = ROOT.TH2F("h_e_nu_kin",
                       ";E_{#nu} [GeV];E_{k}^{true} [GeV]",
                       100, 0, 1, 100, 0, 1)

h_e_res_intervals = []
for i in range(len(bins)-1):
    interval = "{:.2f}-{:.2f} GeV".format(bins[i], bins[i + 1])
    h_e_res_intervals.append(ROOT.TH1F("h_e_res{}".format(i),
                                       "%s;(E_{corr} - E_{true}) / E_{true};N. Entries / 0.04" % interval,
                                       30, -1, 1))

l_true_reco = [[] for i in range(len(bins) - 1)]
h_true_reco_slices = []
for i in range(len(l_true_reco)):
    h = ROOT.TH1F("h%i" % i, "", 100, 0, 2)
    h_true_reco_slices.append(h)

categories = [0, 0, 0, 0, 0, 0, 0, 0]
categories_passed = [0, 0, 0, 0, 0, 0, 0, 0]

PROTON_THRESHOLD = 0.040
ELECTRON_THRESHOLD = 0.020

for evt in range(entries):
    chain.GetEntry(evt)

    p = 0
    e = 0
    photons = 0
    pions = 0
    electron_energy = 0
    proton_energy = 0
    for i, energy in enumerate(chain.nu_daughters_E):
        if abs(chain.nu_daughters_pdg[i]) == 2212:
            if energy - 0.938 > PROTON_THRESHOLD:
                proton_energy += energy - 0.938
                p += 1

        if abs(chain.nu_daughters_pdg[i]) == 11:
            if energy > ELECTRON_THRESHOLD:
                electron_energy += energy
                e += 1

        if chain.nu_daughters_pdg[i] == 22:
            # if energy > 0.035:
            photons += 1

        if chain.nu_daughters_pdg[i] == 111:
            # if energy > 0.06:
            pions += 1

    eNp = e == 1 and photons == 0 and pions == 0 and p > 0

    categories[chain.category] += 1
    if chain.passed:
        categories_passed[chain.category] += 1

    neutrino_vertex = [chain.true_vx, chain.true_vy, chain.true_vz]

    if eNp and bins[0] < chain.nu_E < bins[-1]:
        if is_fiducial(neutrino_vertex):
            total += 1

            if chain.passed and chain.category == 2:

                tot_energy = electron_energy + proton_energy
                hit_index = choose_plane(chain)
                total_shower_energy = sum([chain.shower_energy[i_sh][hit_index] for i_sh in range(chain.n_showers)])
                total_track_energy_length = sum([length2energy(chain.track_len[i_tr]) for i_tr in range(chain.n_tracks)])

                reco_energy = total_shower_energy + total_track_energy_length
                h_e_true_reco.Fill(tot_energy, reco_energy)

                if bins[0] < reco_energy < bins[-1]:
                    h_e_true.Fill(chain.nu_E)
                    h_matrix.Fill(reco_energy, chain.nu_E)

                h_e_reco.Fill(reco_energy)

                h_e_nu_kin.Fill(chain.nu_E, tot_energy)

                e_res = ((reco_energy - (8.49139e-03)) / 7.53310e-01 -
                         tot_energy) / tot_energy

                h_e_res.Fill(e_res)
                if tot_energy < bins[-1]:
                    for i, bin in enumerate(bins):
                        if tot_energy > bin:
                            index = i
                    h_e_res_intervals[index].Fill(e_res)
                    l_true_reco[index].append(reco_energy)
                    h_true_reco_slices[index].Fill(reco_energy)

                else:
                    wrong_event += 1
            else:
                find_track = False
                find_shower = False


print(categories, categories_passed)
print(total, perfect_event, incomplete_event, splitted_event, wrong_event, flash_not_passed)
print("Passed event, perfect {:.1f} %".format(perfect_event / total * 100))
print("Passed event, incomplete {:.1f} %"
      .format(incomplete_event / total * 100))
print("Passed event, splitted {:.1f} %".format(splitted_event / total * 100))
print("Passed event, wrong {:.1f} %".format(wrong_event / total * 100))
print("Not passed event, flash not passed {:.1f}% "
      .format(flash_not_passed / total * 100))
print("Not passed event, flash passed, track ok, shower misid. {:.1f}% "
      .format(track_ok_shower_mis / total * 100))
print("Not passed event, flash passed, shower ok, track misid. {:.1f}% "
      .format(shower_ok_track_mis / total * 100))
print("Not passed event, flash passed, track ok, no shower {:.1f}% "
      .format(track_ok_shower_no / total * 100))
print("Not passed event, flash passed, shower ok, no track {:.1f}% "
      .format(shower_ok_track_no / total * 100))
print("Not passed event, flash passed, no track, no shower {:.1f}% "
      .format(track_no_shower_no / total * 100))

e_values = array("f", ([bins[i]+(bins[i+1]-bins[i])/2 for i in range(len(bins)-1)]))
e_errs = array("f", ([(bins[i+1]-bins[i])/2 for i in range(len(bins)-1)]))

median_values = array("f")
median_errs = array("f")
for h in h_true_reco_slices:
    median_values.append(h.GetMaximumBin() * 0.02 - 0.01)
    print(h.GetMaximumBin(), h.GetMaximum(), h.GetBinContent(h.GetMaximumBin()))
    median_errs.append(h.GetRMS())
print(e_values)

c1 = ROOT.TCanvas("c1")
h_true_reco_slices[2].Draw()
c1.Update()

print(median_values)
g_e_true_reco = ROOT.TGraphErrors(len(median_values),
                                  e_values, median_values, e_errs, median_errs)

a_e_true_reco = np.zeros((len(bins)-1, len(bins)-1))

matrix = h_matrix.Clone()
for i in range(1, h_matrix.GetNbinsX() + 1):
    row_sum = sum([h_matrix.GetBinContent(i, j)
                   for j in range(1, h_matrix.GetNbinsY() + 1)])

    for j in range(1, h_matrix.GetNbinsY() + 1):
        a_e_true_reco[j - 1][i - 1] = h_matrix.GetBinContent(i, j) / row_sum
        matrix.SetBinContent(i, j, h_matrix.GetBinContent(i, j) / row_sum)

c_e_2d = ROOT.TCanvas("c_e_2d")
matrix.GetYaxis().SetTitleOffset(0.9)
matrix.Draw("colz text")

a_e_true = hist2array(h_e_true)
a_e_reco = hist2array(h_e_reco)

true_scaling = np.array([5.015008606, 4.755966764, 4.240843625, 3.494299576,
                         2.596148682, 1.715699034, 1.051751175, 1.051751175,
                         0.896630140, 0.896630140, 0.896630140, 0.896630140,
                         0.913416650, 0.913416650, 0.913416650, 0.913416650])


print("IS WORKING? ", np.dot(a_e_true_reco, a_e_true) == a_e_reco)
print("IS WORKING? ", np.dot(a_e_true_reco, a_e_reco) == a_e_true)
print(np.dot(a_e_true_reco, a_e_reco))
print(a_e_true)
with open("a_e_true_reco.bin", "wb") as f:
    pickle.dump(a_e_true_reco, f, pickle.HIGHEST_PROTOCOL)

h_matrix.GetYaxis().SetTitleOffset(0.8)

c_e_2d.Update()

c_e_lin = ROOT.TCanvas("c_e_lin")
h_e_true_reco.Draw("colz")
h_e_true_reco.GetYaxis().SetTitleOffset(0.9)
g_e_true_reco.Draw("ep same")
g_e_true_reco.SetLineWidth(2)
g_e_true_reco.SetMarkerStyle(20)
f_line = ROOT.TF1("f_line", "[0]*x+[1]", 0, 2)
f_line.SetParNames("m", "q")
l_e_true_reco = ROOT.TLegend(0.099, 0.913, 0.900, 0.968)
l_e_true_reco.SetNColumns(2)
l_e_true_reco.AddEntry(g_e_true_reco, "Most probable values", "lep")
g_e_true_reco.Fit(f_line)
l_e_true_reco.AddEntry(f_line, "E_{k}^{reco} = %.2f E_{k}^{true} + %.2f GeV" %
                       (f_line.GetParameter(0), f_line.GetParameter(1)), "l")
l_e_true_reco.Draw()
c_e_lin.Update()

c_e_res = ROOT.TCanvas("c_e_res")

f_gausexp = ROOT.TF1("f_gausexp", gauss_exp, -1, 1, 4)
h_e_res.Draw("ep")
h_e_res.SetMarkerStyle(20)

f_gausexp.SetParLimits(2, 0.001, 0.6)
f_gausexp.SetParLimits(3, 0.001, 1)
f_gausexp.SetParLimits(1, -0.3, 0.3)
f_gausexp.SetParameters(250, 0, 0.13, 0.18)
f_gausexp.SetParNames("A", "#mu", "#sigma", "k")
h_e_res.Fit(f_gausexp, "RQ", "", -0.6, 0.4)
h_e_res.SetLineColor(ROOT.kBlack)
h_e_res.GetYaxis().SetTitleOffset(0.9)

l_e_res = ROOT.TLegend(0.13, 0.76, 0.47, 0.85)
l_e_res.AddEntry(f_gausexp, "GaussExp fit", "l")
l_e_res.AddEntry(f_gausexp, "#mu = %.2f, #sigma = %.2f, k = %.2f" %
                 (f_gausexp.GetParameter(1),
                 f_gausexp.GetParameter(2),
                 f_gausexp.GetParameter(3)), "")
l_e_res.Draw()

c_e_res.Update()


c_e_res_intervals = ROOT.TCanvas("c_e_res_intervals", "", 1240, 800)
c_e_res_intervals.Divide(3, 3)
ROOT.gStyle.SetOptTitle(1)
ROOT.gStyle.SetTitleFillColor(ROOT.kWhite)
ROOT.gStyle.SetTitleSize(0.6)

legends = []
sigma = []
sigma_err = []


for i in range(len(bins)-1):
    c_e_res_intervals.cd(i+1)
    f_gausexp.SetParameters(h_e_res_intervals[i].GetMaximum(),
                            h_e_res_intervals[i].GetMean(),
                            h_e_res_intervals[i].GetRMS(),
                            0.18)

    h_e_res_intervals[i].Fit(
        f_gausexp, "RQ", "", h_e_res_intervals[i].GetMean() - h_e_res_intervals[i].GetRMS(), max(h_e_res_intervals[i].GetMean() + h_e_res_intervals[i].GetRMS(), 0.3))

    legends.append(ROOT.TLegend(0.58, 0.77, 0.86, 0.85))
    legends[-1].AddEntry(f_gausexp, "#mu = %.2f, #sigma = %.2f, k = %.2f" %
            (f_gausexp.GetParameter(1),
            f_gausexp.GetParameter(2),
            f_gausexp.GetParameter(3)), "")
    sigma.append(f_gausexp.GetParameter(2) * 100)
    sigma_err.append(f_gausexp.GetParError(2) * 100)
    h_e_res_intervals[i].SetMarkerStyle(20)
    h_e_res_intervals[i].SetLineColor(ROOT.kBlack)
    h_e_res_intervals[i].Draw("ep")
    legends[-1].Draw()
c_e_res_intervals.Update()


c_sigmas = ROOT.TCanvas("c_sigmas")
sigma_array = array("f", sigma)
sigma_err_array = array("f", sigma_err)

e_values = array("f", [bins[i] + (bins[i + 1] - bins[i]) / 2
                       for i in range(len(bins) - 1)])
e_errs = array("f", [(bins[i + 1] - bins[i]) / 2
                     for i in range(len(bins) - 1)])

f_res = ROOT.TF1("f_res", "sqrt(([0]/sqrt(x))**2+([1]/x)**2+[2]**2)", 0, 2)
f_res.SetParNames("a", "b", "c")

g_sigma = ROOT.TGraphErrors(len(sigma_array),
                            e_values, sigma_array, e_errs, sigma_err_array)
g_sigma.SetTitle("")
g_sigma.SetMarkerStyle(20)
g_sigma.GetXaxis().SetTitle("E_{true} [GeV]")
g_sigma.GetXaxis().SetTitleSize(0.05)
g_sigma.GetXaxis().SetTitleOffset(0.95)
g_sigma.GetYaxis().SetTitle("#sigma [%]")
g_sigma.Fit(f_res)
g_sigma.Draw("AP")


l_res = ROOT.TLegend(0.37, 0.68, 0.80, 0.86)
l_res.AddEntry(f_res, "(#frac{%.2f}{#sqrt{E / GeV}} #oplus #frac{%.2f}{E / GeV} #oplus %.2f) %%" %
            (f_res.GetParameter(0),
            f_res.GetParameter(1),
            f_res.GetParameter(2)), "l")
l_res.Draw()

c_sigmas.Update()

c_e_nu = ROOT.TCanvas("c_e_nu")
h_e_nu_kin.Draw("colz")
h_e_nu_kin.GetYaxis().SetTitleOffset(0.9)
c_e_nu.Update()

c = ROOT.TCanvas("c")
h_e_true.Draw()
h_e_reco.SetLineColor(ROOT.kRed + 1)
h_e_reco.Draw("same")
c.Update()
input()
