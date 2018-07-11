#!/usr/local/bin/python3

from ROOT import TChain, TTree, TFile, TVector3, TH1F, TCanvas
from ROOT import kRed, kBlue, TMVA
from glob import glob
from array import array
import math
from bdt_common import total_pot, variables, spectators, choose_shower
from bdt_common import x_start, x_end, y_start, y_end, z_start, z_end, is_fiducial
from bdt_common import ELECTRON_MASS, PROTON_MASS, printProgressBar
from proton_energy import length2energy
import time
import statistics


PROTON_THRESHOLD = 0.040
ELECTRON_THRESHOLD = 0.020

TMVA.Tools.Instance()
reader_dqdx = TMVA.Reader(":".join([
    "!V",
    "!Silent",
    "Color"]))
dqdx = array("f", [0])
length = array("f", [0])
reader_dqdx.AddVariable("dqdx", dqdx)
reader_dqdx.AddVariable("len", length)
reader_dqdx.BookMVA("dqdx BDT",
                "dataset/weights/TMVAClassification_dqdx BDT.weights.xml")

reader_dedx = TMVA.Reader(":".join([
    "!V",
    "!Silent",
    "Color"]))
dedx = array("f", [0])
nhits = array("f", [0])
reader_dedx.AddVariable("dedx", dedx)
reader_dedx.AddVariable("nhits", nhits)
reader_dedx.BookMVA("dedx BDT",
                    "dataset/weights/TMVAClassification_dedx BDT.weights.xml")


reader_dqdx_pion = TMVA.Reader(":".join([
    "!V",
    "!Silent",
    "Color"]))
dqdx_pion = array("f", [0])
length_pion = array("f", [0])
reader_dqdx_pion.AddVariable("dqdx", dqdx_pion)
reader_dqdx_pion.AddVariable("len", length_pion)
reader_dqdx_pion.BookMVA("dqdx pion BDT",
                    "dataset/weights/TMVAClassification_dqdx pion BDT.weights.xml")

def min_dqdx_pion(root_chain):
    min_score = 1

    for i_tr in range(root_chain.n_tracks):
        track_dqdx = root_chain.track_dQdx[i_tr][2]
        if root_chain.category == 0 or root_chain.category == 6:
            track_dqdx *= 1.2

        track_length = root_chain.track_len[i_tr]
        score = dqdx_length_pion(track_dqdx, track_length)
        if score < min_score:
            min_score = score

    return min_score

def min_dedx(root_chain):
    min_score = 1

    for i_sh in range(root_chain.n_showers):
        shower_dedx = root_chain.shower_dEdx[i_sh][2]

        shower_hits = root_chain.shower_nhits[i_sh][2]
        score = dedx_hits(shower_dedx, shower_hits)
        if score < min_score:
            min_score = score

    return min_score


def max_dqdx(root_chain):
    max_score = 0

    for i_tr in range(root_chain.n_tracks):
        track_dqdx = root_chain.track_dQdx[i_tr][2]
        if root_chain.category == 0 or root_chain.category == 6:
            track_dqdx *= 1.2

        track_length = root_chain.track_len[i_tr]
        score = dqdx_length(track_dqdx, track_length)
        if score > max_score:
            max_score = score
    
    return max_score


def min_dqdx(root_chain):
    min_score = 1

    for i_tr in range(root_chain.n_tracks):
        track_dqdx = root_chain.track_dQdx[i_tr][2]
        if root_chain.category == 0 or root_chain.category == 6:
            track_dqdx *= 1.2

        track_length = root_chain.track_len[i_tr]
        score = dqdx_length(track_dqdx, track_length)
        if score < min_score:
            min_score = score

    return min_score

def merged_shower_cali(chain, shower_id):
    plane_nhits = [chain.shower_nhits[shower_id][i] for i in range(3)]
    plane_cali = [chain.shower_dQdx_cali[shower_id][i] for i in range(3)]

    num = sum((n * c for n, c in zip(plane_nhits, plane_cali)))
    den = sum(plane_nhits)

    return num/den

def dqdx_length_pion(v_dqdx, v_length):

    if v_dqdx < 0:
        return -1

    dqdx_pion[0] = v_dqdx
    length_pion[0] = v_length

    BDT_response = reader_dqdx_pion.EvaluateMVA("dqdx pion BDT")
    return BDT_response

def merge_dedx_planes(dedx_planes, pitches):

    for i, value in enumerate(dedx_planes):
        if value <= 0:
            del dedx_planes[i]
            del pitches[i]

    if not dedx_planes:
        return dedx_planes[2]

    p_invs = [1./p for p in pitches]
    return sum(dedx * p_inv for dedx, p_inv in zip(dedx_planes, p_invs)) / sum(p_invs)


def merge_dedx_hits(dedx_planes, hits):

    for i, value in enumerate(dedx_planes):
        if value <= 0:
            del dedx_planes[i]
            del hits[i]

    if not dedx_planes:
        return dedx_planes[2]

    return sum(dedx * hit for dedx, hit in zip(dedx_planes, hits)) / sum(hits)

def dqdx_length(v_dqdx, v_length):
    
    if v_dqdx < 0:
        return -1

    dqdx[0] = v_dqdx
    length[0] = v_length

    BDT_response = reader_dqdx.EvaluateMVA("dqdx BDT")
    return BDT_response

def dedx_hits(v_dedx, v_hits):
    if v_dedx < 0:
        return -1

    dedx[0] = v_dedx
    nhits[0] = v_hits
    BDT_response = reader_dedx.EvaluateMVA("dedx BDT")
    return BDT_response

def pi0_mass(root_chain):
    if root_chain.n_showers < 2:
        return -1
    
    shower_energies = sorted(
        [e[2] for e in root_chain.shower_energy], reverse=True)
    shower_ids = []
    
    for i_sh in range(root_chain.n_showers):
        if root_chain.shower_energy[i_sh][2] in shower_energies:
            shower_ids.append(i_sh)

    v_1 = TVector3(
        root_chain.shower_dir_x[shower_ids[0]],
        root_chain.shower_dir_y[shower_ids[0]],
        root_chain.shower_dir_z[shower_ids[0]])
      
    v_2 = TVector3(
        root_chain.shower_dir_x[shower_ids[1]],
        root_chain.shower_dir_y[shower_ids[1]],
        root_chain.shower_dir_z[shower_ids[1]])

    cos = v_1.Dot(v_2) / (v_1.Mag() * v_2.Mag())
    angle = math.acos(cos)

    e1 = root_chain.shower_energy[shower_ids[0]][2]
    e2 = root_chain.shower_energy[shower_ids[1]][2]

    for i_sh in range(root_chain.n_showers):

        if i_sh in shower_ids:
            continue

        v_x = TVector3(
            root_chain.shower_dir_x[i_sh],
            root_chain.shower_dir_y[i_sh],
            root_chain.shower_dir_z[i_sh])
        
        cos_1 = v_x.Dot(v_1) / (v_x.Mag() * v_1.Mag())
        cos_2 = v_x.Dot(v_2) / (v_x.Mag() * v_2.Mag())
        if math.acos(cos_1) < math.acos(cos_2):
            e1 += root_chain.shower_energy[i_sh][2]
        else:
            e2 += root_chain.shower_energy[i_sh][2]
            
    pi0_mass = math.sqrt(4 * e1 * e2 * (math.sin(angle / 2)**2))

    return pi0_mass

def is_active(point):
    ok_y = y_start < point[1] < y_end
    ok_x = x_start < point[0] < x_end
    ok_z = z_start < point[2] < z_end
    return ok_y and ok_x and ok_z


def choose_track(root_chain):
    max_score = 0
    chosen_track = 0

    for i_tr in range(root_chain.n_tracks):
        track_dqdx = root_chain.track_dQdx[i_tr][2]
        if root_chain.category == 0 or root_chain.category == 6:
            track_dqdx *= 1.2

        track_length = root_chain.track_len[i_tr]
        score = dqdx_length(track_dqdx, track_length)
        if score > max_score:
            max_score = score
            chosen_track = i_tr

    return chosen_track


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

    product = [s for t, s in zip(track_hits, shower_hits)]

    return product.index(max(product))

def distance(p1, p2):
    return math.sqrt(
        sum([(t - n)**2 for t, n in zip(p1, p2)]))

def fill_kin_branches(root_chain, weight, variables, option=""):
    no_tracks = False
    longest_track = 0
    longest_track_id = 0
    hit_index = 2#choose_plane(root_chain)
    shower_id = choose_shower(root_chain, hit_index)
    track_id = choose_track(root_chain)
    variables["E_dep"][0] = 0

    if "nue" in option:
        for i, energy in enumerate(root_chain.nu_daughters_E):
            if root_chain.nu_daughters_pdg[i] == 2212:
                if energy - 0.938 > PROTON_THRESHOLD:
                    variables["E_dep"][0] += energy - 0.938

            if root_chain.nu_daughters_pdg[i] == 11:
                if energy - 0.51e-3 > ELECTRON_THRESHOLD:
                    variables["E_dep"][0] += energy - 0.51e-3

    track_like_shower_id = -1
    if root_chain.n_tracks == 0 and root_chain.n_showers > 1:
        shower_res_std_list = list(root_chain.shower_res_std)
        shower_res_std_list.pop(shower_id)
        track_like_shower_id = shower_res_std_list.index(min(shower_res_std_list))

        no_tracks = True

    for itrk in range(root_chain.n_tracks):
        if root_chain.track_len[itrk] > longest_track:
            longest_track = root_chain.track_len[itrk]
            longest_track_id = itrk

    if no_tracks:
        v_track = TVector3(
            root_chain.shower_dir_x[track_like_shower_id],
            root_chain.shower_dir_y[track_like_shower_id],
            root_chain.shower_dir_z[track_like_shower_id])
    else:
        v_track = TVector3(
            root_chain.track_dir_x[track_id],
            root_chain.track_dir_y[track_id],
            root_chain.track_dir_z[track_id])

    vec_shower = TVector3(
        root_chain.shower_dir_x[shower_id],
        root_chain.shower_dir_y[shower_id],
        root_chain.shower_dir_z[shower_id])

    costheta_shower_track = v_track.Dot(
        vec_shower) / (v_track.Mag() * vec_shower.Mag())

    signal = 0
    if root_chain.category == 2:
        signal = 1

    if no_tracks:
        track_vertex = [
            root_chain.shower_start_x[track_like_shower_id],
            root_chain.shower_start_y[track_like_shower_id],
            root_chain.shower_start_z[track_like_shower_id]]
    else:
        track_vertex = [
            root_chain.track_start_x[track_id],
            root_chain.track_start_y[track_id],
            root_chain.track_start_z[track_id]]

    if no_tracks:
        length = root_chain.shower_length[track_like_shower_id]
        
        shower_end_x = root_chain.shower_start_x[track_like_shower_id] + \
                       length * root_chain.shower_dir_x[track_like_shower_id]

        shower_end_y = root_chain.shower_start_y[track_like_shower_id] + \
                       length * root_chain.shower_dir_y[track_like_shower_id]

        shower_end_z = root_chain.shower_start_z[track_like_shower_id] + \
                       length * root_chain.shower_dir_z[track_like_shower_id]

        track_end = [
            shower_end_x,
            shower_end_y,
            shower_end_z]
    else:
        track_end = [
            root_chain.track_end_x[track_id],
            root_chain.track_end_y[track_id],
            root_chain.track_end_z[track_id]]
    shower_vertex = [
        root_chain.shower_start_x[shower_id],
        root_chain.shower_start_y[shower_id],
        root_chain.shower_start_z[shower_id]]

    true_vertex = [root_chain.true_vx_sce, root_chain.true_vy_sce, root_chain.true_vz_sce]
    neutrino_vertex = [root_chain.vx, root_chain.vy, root_chain.vz]

    shower_vertex_d = math.sqrt(
        sum([(s - n)**2 for s, n in zip(shower_vertex, neutrino_vertex)]))
    track_vertex_d = math.sqrt(
        sum([(t - n)**2 for t, n in zip(track_vertex, neutrino_vertex)]))

    variables["is_signal"][0] = signal
    variables["true_nu_is_fidvol"][0] = int(is_fiducial(true_vertex))

    total_shower_nhits = sum([root_chain.shower_nhits[i_sh][hit_index] for i_sh in range(root_chain.n_showers)])
    total_shower_nhits_y = sum([root_chain.shower_nhits[i_sh][2] for i_sh in range(root_chain.n_showers)])

    variables["n_objects"][0] = root_chain.n_tracks + root_chain.n_showers
    variables["no_tracks"][0] = int(no_tracks)

    if no_tracks:
        variables["track_length"][0] = root_chain.shower_length[track_like_shower_id]
        variables["track_phi"][0] = math.degrees(root_chain.shower_phi[track_like_shower_id])
        variables["track_theta"][0] = math.degrees(root_chain.shower_theta[track_like_shower_id])
        variables["track_start_x"][0] = root_chain.shower_start_x[track_id]
        variables["track_start_y"][0] = root_chain.shower_start_y[track_id]
        variables["track_start_z"][0] = root_chain.shower_start_z[track_id]
        total_track_energy = root_chain.shower_energy[track_like_shower_id][2]
        total_track_energy_y = root_chain.shower_energy[track_like_shower_id][2]
        total_track_nhits = root_chain.shower_nhits[track_like_shower_id][2]
        total_shower_nhits_y -= root_chain.shower_nhits[track_like_shower_id][2]
        total_shower_nhits -= total_track_nhits
        # total_track_energy_length = length2energy(root_chain.shower_length[track_like_shower_id])
        variables["track_energy"][0] = total_track_energy
        # variables["proton_score"][0] = 1
        variables["track_pca"][0] = max(0, root_chain.shower_pca[track_like_shower_id])
        variables["n_tracks"][0] = 1
        variables["n_showers"][0] = root_chain.n_showers - 1
        track_dedx = root_chain.shower_dEdx[track_like_shower_id][2]
        variables["track_dedx"][0] = 9999#max(0, track_dedx)
        variables["track_energy_length"][0] = length2energy(root_chain.shower_length[track_like_shower_id])
        variables["track_res_mean"][0] = -999
        variables["track_res_std"][0] = -999
        variables["track_pidchi"][0] = -999
        variables["track_pidchipr"][0] = -999
        variables["dqdx_bdt"][0] = 1
        variables["dqdx_bdt_max"][0] = 1
        # variables["dqdx_pion"][0] = 1
        # variables["track_pdg"][0] = root_chain.matched_showers[track_like_shower_id]

        dqdx_length(
            root_chain.shower_dQdx[track_like_shower_id][2],
            root_chain.shower_length[track_like_shower_id])
    else:
        variables["track_res_mean"][0] = max(-999, root_chain.track_res_mean[track_id])
        variables["track_res_std"][0] = max(-999, root_chain.track_res_std[track_id])
        variables["track_pidchi"][0] = -999#max(-999, root_chain.track_pidchi[track_id])
        variables["track_pidchipr"][0] = -999#max(-999, root_chain.track_pidchipr[track_id])
        variables["track_length"][0] = root_chain.track_len[longest_track_id]
        variables["track_phi"][0] = math.degrees(root_chain.track_phi[track_id])
        variables["track_theta"][0] = math.degrees(root_chain.track_theta[track_id])
        variables["track_start_x"][0] = root_chain.track_start_x[track_id]
        variables["track_start_y"][0] = root_chain.track_start_y[track_id]
        variables["track_start_z"][0] = root_chain.track_start_z[track_id]
        # total_track_energy_length = sum(
        #     [length2energy(root_chain.track_len[i_tr]) for i_tr in range(root_chain.n_tracks)])
        total_track_energy = sum(
            [root_chain.track_energy_hits[i_tr][2] for i_tr in range(root_chain.n_tracks)])
        total_track_nhits = sum(
            [root_chain.track_nhits[i_tr][2] for i_tr in range(root_chain.n_tracks)])
        variables["track_energy"][0] = root_chain.track_energy_hits[track_id][2]
        # variables["proton_score"][0] = max(0, root_chain.predict_p[track_id])
        variables["track_pca"][0] = max(0, root_chain.track_pca[track_id])
        variables["n_tracks"][0] = root_chain.n_tracks
        variables["n_showers"][0] = root_chain.n_showers
        track_dedx = root_chain.track_dQdx[longest_track_id][2]
        if option == "ext_data" or option == "bnb_data":
            variables["track_dedx"][0] = max(0, track_dedx * 1.2)
        else:
            variables["track_dedx"][0] = max(0, track_dedx)

        variables["track_energy_length"][0] = length2energy(root_chain.track_len[track_id])
        variables["dqdx_bdt"][0] = min_dqdx(root_chain)
        # variables["dqdx_pion"][0] = min_dqdx_pion(root_chain)
        # variables["track_pdg"][0] = root_chain.matched_tracks[track_id]

        variables["dqdx_bdt_max"][0] = max_dqdx(root_chain)

    # variables["shower_pdg"][0] = root_chain.matched_showers[shower_id]
    variables["shower_res_mean"][0] = max(-99999, root_chain.shower_res_mean[shower_id])
    variables["shower_res_std"][0] = max(-99999, root_chain.shower_res_std[shower_id])

    variables["dedx_bdt"][0] =  dedx_hits(
        root_chain.shower_dEdx[shower_id][2],
        root_chain.shower_nhits[shower_id][2])
    
    variables["nu_E"][0] = max(-1, root_chain.nu_E)
    # variables["shower_length"][0] = root_chain.shower_length[shower_id]
    variables["track_end_x"][0] = track_end[0]
    variables["track_end_y"][0] = track_end[1]
    variables["track_end_z"][0] = track_end[2]
    variables["track_distance"][0] = shower_vertex_d
    variables["shower_distance"][0] = track_vertex_d
    variables["shower_start_x"][0] = root_chain.shower_start_x[shower_id]
    # variables["shower_end_x"][0] = root_chain.shower_end_x[shower_id]
    variables["shower_start_y"][0] = root_chain.shower_start_y[shower_id]
    # variables["shower_end_y"][0] = root_chain.shower_end_y[shower_id]
    variables["shower_start_z"][0] = root_chain.shower_start_z[shower_id]
    # variables["shower_end_z"][0] = root_chain.shower_end_z[shower_id]

    total_dedx_hits = []
    for ish in range(root_chain.n_showers):
        if ish != track_like_shower_id:
            total_dedx_hits += root_chain.shower_dEdx_hits[ish]

    dedx_y = 0
    if total_dedx_hits:
        dedx_y = statistics.median(total_dedx_hits)

    variables["shower_track_d"][0] = distance(shower_vertex, track_vertex)
    variables["total_track_energy"][0] = total_track_energy
    # variables["total_track_energy_length"][0] = total_track_energy_length
    variables["track_hits"][0] = total_track_nhits
    variables["shower_hits"][0] = total_shower_nhits
    variables["shower_hits_y"][0] = total_shower_nhits_y
    variables["hits_ratio"][0] = total_shower_nhits/(total_track_nhits+total_shower_nhits)
    variables["shower_energy"][0] = root_chain.shower_energy[shower_id][hit_index]
    variables["shower_energy_y"][0] = root_chain.shower_energy[shower_id][2]
    variables["shower_theta"][0] = math.degrees(root_chain.shower_theta[shower_id])
    variables["shower_phi"][0] = math.degrees(root_chain.shower_phi[shower_id])

    y_shower = sum([root_chain.shower_nhits[i_sh][2] for i_sh in range(root_chain.n_showers)])
    y_track = sum([root_chain.track_nhits[i_sh][2]for i_sh in range(root_chain.n_tracks)])

    u_shower = sum([root_chain.shower_nhits[i_sh][0] for i_sh in range(root_chain.n_showers)])
    u_track = sum([root_chain.track_nhits[i_sh][0] for i_sh in range(root_chain.n_tracks)])

    v_shower = sum([root_chain.shower_nhits[i_sh][1] for i_sh in range(root_chain.n_showers)])
    v_trackh = sum([root_chain.track_nhits[i_sh][1] for i_sh in range(root_chain.n_tracks)])

    variables["total_hits"][0] = u_shower + u_track + v_shower + v_trackh + y_shower + y_track

    variables["total_hits_u"][0] = u_shower + u_track
    variables["total_hits_v"][0] = v_shower + v_trackh
    variables["total_hits_y"][0] = y_shower + y_track

    if option == "cosmic_mc" or option == "ext_data":
        variables["category"][0] = 0
    elif option == "lee":
        variables["category"][0] = 10
    elif option == "nue_cc":
        variables["category"][0] = 8
    else:
        variables["category"][0] = root_chain.category

    variables["event_weight"][0] = weight

    if option == "nue":
        if root_chain.cosmic_fraction > 0.5 and root_chain.category == 7:
            variables["category"][0] = 2

    # if variables["category"][0] == 2:
    #     variables["event_weight"][0] = weight * 1.325

    variables["pt"][0] = pt_plot(root_chain, 2)
    variables["track_shower_angle"][0] = costheta_shower_track
    variables["event"][0] = root_chain.event
    variables["run"][0] = root_chain.run
    variables["subrun"][0] = root_chain.subrun
    variables["interaction_type"][0] = root_chain.interaction_type
    variables["shower_open_angle"][0] = math.degrees(root_chain.shower_open_angle[shower_id])
    variables["shower_pca"][0] = max(0, root_chain.shower_pca[shower_id])
    variables["reco_energy"][0] = 0
    variables["shower_angle"][0] = -1

    total_shower_energy = 0
    total_shower_energy_cali = 0

    total_track_energy_length = 0
    max_pca = 0


    for i_sh in range(root_chain.n_showers):
        shower_v = [root_chain.shower_start_x[i_sh],
                         root_chain.shower_start_y[i_sh],
                         root_chain.shower_start_z[i_sh]]

        v_sh = TVector3(
            root_chain.shower_dir_x[i_sh],
            root_chain.shower_dir_y[i_sh],
            root_chain.shower_dir_z[i_sh])


        cos = v_sh.Dot(vec_shower) / (v_sh.Mag() * vec_shower.Mag())
        shower_angle = math.degrees(math.acos(min(cos, 1)))
        if root_chain.n_showers == 2:
            if i_sh != shower_id:
                variables["shower_angle"][0] = shower_angle

        if root_chain.shower_pca[i_sh] > max_pca:
            max_pca = root_chain.shower_pca[i_sh]

        if i_sh != shower_id and (70 < shower_angle < 160 or root_chain.shower_pca[i_sh] > 0.985) or root_chain.shower_res_std[i_sh] < 0.2:
            length_e = length2energy(root_chain.shower_length[i_sh])
            variables["reco_energy"][0] += length_e
            total_track_energy_length += length_e
            # variables["n_tracks"][0] += 1
            # variables["n_showers"][0] -= 1
        else:
            variables["reco_energy"][0] += root_chain.shower_energy[i_sh][hit_index]
            total_shower_energy += root_chain.shower_energy[i_sh][hit_index]
            total_shower_energy_cali += root_chain.shower_energy[i_sh][hit_index] * \
                root_chain.shower_energy_cali[i_sh][hit_index]


    for i_tr in range(root_chain.n_tracks):

        v_tr = TVector3(
            root_chain.track_dir_x[i_tr],
            root_chain.track_dir_y[i_tr],
            root_chain.track_dir_z[i_tr])

        cos = v_tr.Dot(v_track) / (v_tr.Mag() * v_track.Mag())

        if root_chain.track_pca[i_tr] < max_pca:
            variables["reco_energy"][0] += root_chain.track_energy_hits[i_tr][hit_index]
            total_shower_energy += root_chain.track_energy_hits[i_tr][hit_index]
            total_shower_energy_cali += root_chain.track_energy_hits[i_tr][hit_index] * root_chain.track_energy_cali[i_tr][hit_index]

            # variables["n_tracks"][0] -= 1
            # variables["n_showers"][0] += 1
        else:
            length_e = length2energy(root_chain.track_len[i_tr])
            variables["reco_energy"][0] += length_e
            total_track_energy_length += length_e

    variables["total_shower_energy"][0] = total_shower_energy
    variables["total_shower_energy_cali"][0] = total_shower_energy_cali

    variables["total_track_energy_length"][0] = total_track_energy_length
    variables["numu_score"][0] = root_chain.numu_cuts

    # dE/dx for the collection plane only

    dedx_merged = statistics.median(list(root_chain.shower_dEdx_hits[shower_id])) * merged_shower_cali(root_chain, shower_id)

    dedx_cali = root_chain.shower_dEdx[shower_id][2] * root_chain.shower_dQdx_cali[shower_id][2]
    dedx = root_chain.shower_dEdx[shower_id][2]
    dedx_u = root_chain.shower_dEdx[shower_id][0] * root_chain.shower_dQdx_cali[shower_id][0]
    dedx_v = root_chain.shower_dEdx[shower_id][1] * root_chain.shower_dQdx_cali[shower_id][1]

    variables["shower_energy"][0] = root_chain.shower_energy[shower_id][2] * root_chain.shower_energy_cali[shower_id][2]
    variables["dedx_cali"][0] = max(-1, dedx_cali)
    variables["dedx"][0] = max(-1, dedx)
    variables["dedx_u"][0] = max(-1, dedx_u)
    variables["dedx_v"][0] = max(-1, dedx_v)
    variables["dedx_merged"][0] = max(-1, dedx_merged)


def pt_plot(root_chain, plane):
    p_showers = []
    for ish in range(root_chain.n_showers):
        if root_chain.shower_energy[ish][plane] > 0:
            p_vector = TVector3(
                root_chain.shower_dir_x[ish],
                root_chain.shower_dir_y[ish],
                root_chain.shower_dir_z[ish])
            if root_chain.shower_energy[ish][plane] < 10:
                p_vector.SetMag(
                    math.sqrt(
                        (root_chain.shower_energy[ish][plane] + ELECTRON_MASS)**2 - ELECTRON_MASS**2))
            p_showers.append(p_vector)

    p_tracks = []
    for itr in range(root_chain.n_tracks):
        if root_chain.track_energy_hits[itr][plane] > 0:
            p_vector = TVector3(
                root_chain.track_dir_x[itr],
                root_chain.track_dir_y[itr],
                root_chain.track_dir_z[itr])
            p_vector.SetMag(
                math.sqrt(
                    (root_chain.track_energy_hits[itr][plane] +
                     PROTON_MASS)**2 -
                    PROTON_MASS**2))
            p_tracks.append(p_vector)

    p_track_sum = TVector3()
    if p_tracks:
        p_track_sum = p_tracks[0]
        for itr in p_tracks[1:]:
            p_track_sum += itr

    p_shower_sum = TVector3()
    if p_showers:
        p_shower_sum = p_showers[0]
        for ish in p_showers[1:]:
            p_shower_sum += ish

    pt = (p_track_sum + p_shower_sum).Perp()
    return pt


def fill_tree(chain, weight, tree, option=""):
    total_events = 0
    total_entries = int(chain.GetEntries() / 1)

    for ievt in range(total_entries):
        chain.GetEntry(ievt)
        printProgressBar(ievt, total_entries, prefix="Progress:", suffix="Complete", length = 20)

        if chain.passed:

            track_fidvol = True

            for i_tr in range(chain.n_tracks):
                track_start = [
                    chain.track_start_x[i_tr],
                    chain.track_start_y[i_tr],
                    chain.track_start_z[i_tr]]
                track_end = [
                    chain.track_end_x[i_tr],
                    chain.track_end_y[i_tr],
                    chain.track_end_z[i_tr]]

                track_fidvol = track_fidvol and is_fiducial(track_start) and is_fiducial(track_end)

            shower_fidvol = True

            for i_sh in range(chain.n_showers):
                shower_start = [
                    chain.shower_start_x[i_sh],
                    chain.shower_start_y[i_sh],
                    chain.shower_start_z[i_sh]]

                shower_fidvol = shower_fidvol and is_fiducial(shower_start)

            option_check = True
            event_weight = weight

            if option == "bnb":
                option_check = abs(chain.nu_pdg) != 12
            if abs(chain.nu_pdg) == 12:
                event_weight = weight * chain.bnbweight 
            if "nue" in option:
                option_check = abs(chain.nu_pdg) == 12

            neutrino_vertex = [chain.vx, chain.vy, chain.vz]

            # If there are no tracks we require at least two showers
            showers_2_tracks_0 = True
            if chain.n_tracks == 0 and chain.n_showers == 1:
                showers_2_tracks_0 = False

            is_data = option == "bnb_data" or option == "ext_data"

            perfect_reconstruction = True 
            if (2212 not in chain.matched_tracks or 11 not in chain.matched_showers or 2212 in chain.matched_showers or 11 in chain.matched_tracks) and not is_data:
                perfect_reconstruction = False 

            if option_check and is_fiducial(neutrino_vertex) and track_fidvol and shower_fidvol and showers_2_tracks_0:
                total_events += event_weight

                if "nue" in option and chain.category == 2:
                    if 2212 not in chain.nu_daughters_pdg or abs(111) in chain.nu_daughters_pdg or abs(211) in chain.nu_daughters_pdg:
                        option = "nue_cc"
                    else:
                        option = "nue"

                fill_kin_branches(chain, event_weight, variables, option)
                tree.Fill()

    return total_events

begin_time = time.time()
# To be obtained with Zarko's POT tool
data_ext_scaling_factor = 0.1327933846  # Sample with remapped PMTs

samples = ["cosmic_mc", "nue", "bnb", "bnb_data", "ext_data", "lee"]

tree_files = [glob("cosmic_intime_mcc86/*/a*.root"),
              glob("mc_nue_crhit/*.root"),
              glob("mc_bnb_newcrhit/*/*.root"),
              glob("data_bnb_newcrhit/*/*.root"),
              glob("data_ext_newcrhit/*/*.root"),
              glob("lee/*a.root")]

chains = []
chains_pot = []
for i, files in enumerate(tree_files):
    chains.append(TChain("robertoana/pandoratree"))
    chains_pot.append(TChain("robertoana/pot"))

    for j, f in enumerate(files):
        chains[i].Add(f)
        chains_pot[i].Add(f)

pots = []
for k, c in enumerate(chains_pot):
    total_pot_file = 0
    for i in range(c.GetEntries()):
        c.GetEntry(i)
        total_pot_file += c.pot

    pots.append(total_pot_file)

pots_dict = dict(zip(samples, pots))
chains_dict = dict(zip(samples, chains))
chains_pot_dict = dict(zip(samples, chains_pot))
variables = dict(variables + spectators)
# pots_dict["nue"] = 1
# pots_dict["bnb"] = 3.91300146e19
pots_dict["lee"] = 1

weights = [1,
           total_pot / pots_dict["nue"] * 1.028, # Position of the detector is slightly wrong
           total_pot / pots_dict["bnb"] * 1.028,
           1,
           data_ext_scaling_factor,
           total_pot / pots_dict["lee"]]
print(weights)
files = ["cosmic_mc_file.root", "nue_file.root", "mc_file.root",
         "bnb_file.root", "bnbext_file.root", "lee_file.root"]
tree_names = ["cosmic_mc_tree", "nue_tree", "mc_tree",
              "bnb_tree", "bnbext_tree", "lee_tree"]

trees = []

for t in tree_names:
    trees.append(TTree(t, t))

for n, b in variables.items():
    for t in trees:
        t.Branch(n, b, n + "/f")

samples = ["cosmic_mc", "nue", "bnb", "bnb_data", "ext_data", "lee"]

run_subrun_bnb = open("run_subrun_bnb.txt", "w")

print("Writing run/subrun/events for BNB and EXT...")
for i in range(chains_pot_dict["bnb_data"].GetEntries()):
    chains_pot_dict["bnb_data"].GetEntry(i)
    run_subrun = "%i %i" % (chains_pot_dict["bnb_data"].run,
                            chains_pot_dict["bnb_data"].subrun)
    print(run_subrun, file=run_subrun_bnb)

run_subrun_bnb.close()

run_subrun_ext = open("run_subrun_ext.txt", "w")
for i in range(chains_pot_dict["ext_data"].GetEntries()):
    chains_pot_dict["ext_data"].GetEntry(i)
    run_subrun = "%i %i" % (chains_pot_dict["ext_data"].run,
                            chains_pot_dict["ext_data"].subrun)
    print(run_subrun, file=run_subrun_ext)

run_subrun_ext.close()

for i, s in enumerate(samples):
    start_time = time.time()
    print("******************************")
    print("Sample", s)
    print("Weight", weights[i])
    events = fill_tree(chains[i], weights[i], trees[i], s)
    print("\nEvents", events)
    print("Time to fill %.1f s"  % (time.time() - start_time))

for f, t in zip(files, trees):
    tfile = TFile("root_files/" + f, "RECREATE")
    t.Write()
    tfile.Close()

print("Total time %.2f" % (time.time() - begin_time))


