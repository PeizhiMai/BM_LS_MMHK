#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

#include "qbasis.h"

// Independent 4x2 full-Hilbert-space check of the UV observable definitions.
// Only N_up and N_down are fixed; no total-momentum sector is imposed.
int main(int argc, char* argv[]) {
    if (argc != 1 && argc != 7) {
        std::cerr << "Usage: " << argv[0]
                  << " [U V tp phi_x phi_y output.dat]" << std::endl;
        return 1;
    }

    const double U = (argc == 7) ? std::atof(argv[1]) : 8.0;
    const double V = (argc == 7) ? std::atof(argv[2]) : 1.6;
    const double tp = (argc == 7) ? std::atof(argv[3]) : 0.0;
    const double phi_x = (argc == 7) ? std::atof(argv[4]) : 0.37;
    const double phi_y = (argc == 7) ? std::atof(argv[5]) : 0.23;
    const std::string output_name =
        (argc == 7) ? argv[6] : "check_4x2_full_ed_observables_UV.dat";

    qbasis::initialize();
    std::cout << std::setprecision(12);

    constexpr double t = 1.0;
    constexpr int Lx = 4;
    constexpr int Ly = 2;
    constexpr int Nsites_int = Lx * Ly;
    constexpr double Nup_total = 4.0;
    constexpr double Ndn_total = 4.0;
    constexpr double Ntotal = Nup_total + Ndn_total;
    const double Nsites = static_cast<double>(Nsites_int);
    const double density = Ntotal / Nsites;
    const double inv_sqrt_Nsites = 1.0 / std::sqrt(Nsites);

    const double cx = std::cos(phi_x);
    const double sx = std::sin(phi_x);
    const double cy = std::cos(phi_y);
    const double sy = std::sin(phi_y);
    const double cxpy = std::cos(phi_x + phi_y);
    const double sxpy = std::sin(phi_x + phi_y);
    const double cxmy = std::cos(phi_x - phi_y);
    const double sxmy = std::sin(phi_x - phi_y);

    std::vector<std::string> bc{"pbc", "pbc"};
    qbasis::lattice lattice(
        "square",
        {static_cast<uint32_t>(Lx), static_cast<uint32_t>(Ly)},
        bc
    );

    auto c_up = std::vector<std::vector<std::complex<double>>>(
        4, std::vector<std::complex<double>>(4, 0.0)
    );
    auto c_dn = c_up;
    c_up[0][1] = std::complex<double>(1.0, 0.0);
    c_up[2][3] = std::complex<double>(1.0, 0.0);
    c_dn[0][2] = std::complex<double>(1.0, 0.0);
    c_dn[1][3] = std::complex<double>(-1.0, 0.0);

    qbasis::model<std::complex<double>> Hubbard(lattice);
    Hubbard.add_orbital(lattice.Nsites, "electron");

    qbasis::mopr<std::complex<double>> Nup;
    qbasis::mopr<std::complex<double>> Ndown;
    qbasis::mopr<std::complex<double>> double_occupancy_sum;
    qbasis::mopr<std::complex<double>> nn_density_sum;
    qbasis::mopr<std::complex<double>> spin_nn_sum;
    qbasis::mopr<std::complex<double>> kinetic_nn;
    qbasis::mopr<std::complex<double>> kinetic_nnn;
    qbasis::mopr<std::complex<double>> charge_pipi;
    qbasis::mopr<std::complex<double>> spinz_pipi;
    qbasis::mopr<std::complex<double>> c_up_q0;
    qbasis::mopr<std::complex<double>> c_dn_q0;
    int num_nn_bonds = 0;

    for (int x = 0; x < Lx; ++x) {
        for (int y = 0; y < Ly; ++y) {
            uint32_t site_i, site_j;
            std::vector<int> work(lattice.dim);
            lattice.coor2site({x, y}, 0, site_i, work);

            auto c_up_i = qbasis::opr<std::complex<double>>(site_i, 0, true, c_up);
            auto c_dn_i = qbasis::opr<std::complex<double>>(site_i, 0, true, c_dn);
            auto c_up_dg_i = c_up_i;
            auto c_dn_dg_i = c_dn_i;
            c_up_dg_i.dagger();
            c_dn_dg_i.dagger();
            auto n_up_i = c_up_dg_i * c_up_i;
            auto n_dn_i = c_dn_dg_i * c_dn_i;
            auto n_i = n_up_i + n_dn_i;
            auto sz_i = std::complex<double>(0.5, 0.0) * (n_up_i - n_dn_i);
            auto sp_i = c_up_dg_i * c_dn_i;
            auto sm_i = c_dn_dg_i * c_up_i;

            Nup += n_up_i;
            Ndown += n_dn_i;
            double_occupancy_sum += n_up_i * n_dn_i;

            const double staggered_sign = ((x + y) % 2 == 0) ? 1.0 : -1.0;
            charge_pipi += std::complex<double>(
                staggered_sign * inv_sqrt_Nsites, 0.0
            ) * n_i;
            spinz_pipi += std::complex<double>(
                0.5 * staggered_sign * inv_sqrt_Nsites, 0.0
            ) * (n_up_i - n_dn_i);
            c_up_q0 += std::complex<double>(inv_sqrt_Nsites, 0.0) * c_up_i;
            c_dn_q0 += std::complex<double>(inv_sqrt_Nsites, 0.0) * c_dn_i;

            // +x nearest-neighbor bond.
            lattice.coor2site({x + 1, y}, 0, site_j, work);
            auto c_up_j_x = qbasis::opr<std::complex<double>>(site_j, 0, true, c_up);
            auto c_dn_j_x = qbasis::opr<std::complex<double>>(site_j, 0, true, c_dn);
            auto c_up_dg_j_x = c_up_j_x;
            auto c_dn_dg_j_x = c_dn_j_x;
            c_up_dg_j_x.dagger();
            c_dn_dg_j_x.dagger();
            auto n_up_j_x = c_up_dg_j_x * c_up_j_x;
            auto n_dn_j_x = c_dn_dg_j_x * c_dn_j_x;
            auto n_j_x = n_up_j_x + n_dn_j_x;
            auto sz_j_x = std::complex<double>(0.5, 0.0) * (n_up_j_x - n_dn_j_x);
            auto sp_j_x = c_up_dg_j_x * c_dn_j_x;
            auto sm_j_x = c_dn_dg_j_x * c_up_j_x;

            auto hop_up_x_f = std::complex<double>(-t * cx, -t * sx) *
                              (c_up_dg_i * c_up_j_x);
            auto hop_up_x_b = std::complex<double>(-t * cx, t * sx) *
                              (c_up_dg_j_x * c_up_i);
            auto hop_dn_x_f = std::complex<double>(-t * cx, -t * sx) *
                              (c_dn_dg_i * c_dn_j_x);
            auto hop_dn_x_b = std::complex<double>(-t * cx, t * sx) *
                              (c_dn_dg_j_x * c_dn_i);
            Hubbard.add_Ham(hop_up_x_f);
            Hubbard.add_Ham(hop_up_x_b);
            Hubbard.add_Ham(hop_dn_x_f);
            Hubbard.add_Ham(hop_dn_x_b);
            kinetic_nn += hop_up_x_f + hop_up_x_b + hop_dn_x_f + hop_dn_x_b;
            Hubbard.add_Ham(std::complex<double>(V, 0.0) * (n_i * n_j_x));
            nn_density_sum += n_i * n_j_x;
            spin_nn_sum += sz_i * sz_j_x
                         + std::complex<double>(0.5, 0.0) *
                           (sp_i * sm_j_x + sm_i * sp_j_x);
            ++num_nn_bonds;

            // +y nearest-neighbor bond.  On the 4x2 torus the two y bonds
            // connecting a site pair are distinct periodic lattice bonds.
            lattice.coor2site({x, y + 1}, 0, site_j, work);
            auto c_up_j_y = qbasis::opr<std::complex<double>>(site_j, 0, true, c_up);
            auto c_dn_j_y = qbasis::opr<std::complex<double>>(site_j, 0, true, c_dn);
            auto c_up_dg_j_y = c_up_j_y;
            auto c_dn_dg_j_y = c_dn_j_y;
            c_up_dg_j_y.dagger();
            c_dn_dg_j_y.dagger();
            auto n_up_j_y = c_up_dg_j_y * c_up_j_y;
            auto n_dn_j_y = c_dn_dg_j_y * c_dn_j_y;
            auto n_j_y = n_up_j_y + n_dn_j_y;
            auto sz_j_y = std::complex<double>(0.5, 0.0) * (n_up_j_y - n_dn_j_y);
            auto sp_j_y = c_up_dg_j_y * c_dn_j_y;
            auto sm_j_y = c_dn_dg_j_y * c_up_j_y;

            auto hop_up_y_f = std::complex<double>(-t * cy, -t * sy) *
                              (c_up_dg_i * c_up_j_y);
            auto hop_up_y_b = std::complex<double>(-t * cy, t * sy) *
                              (c_up_dg_j_y * c_up_i);
            auto hop_dn_y_f = std::complex<double>(-t * cy, -t * sy) *
                              (c_dn_dg_i * c_dn_j_y);
            auto hop_dn_y_b = std::complex<double>(-t * cy, t * sy) *
                              (c_dn_dg_j_y * c_dn_i);
            Hubbard.add_Ham(hop_up_y_f);
            Hubbard.add_Ham(hop_up_y_b);
            Hubbard.add_Ham(hop_dn_y_f);
            Hubbard.add_Ham(hop_dn_y_b);
            kinetic_nn += hop_up_y_f + hop_up_y_b + hop_dn_y_f + hop_dn_y_b;
            Hubbard.add_Ham(std::complex<double>(V, 0.0) * (n_i * n_j_y));
            nn_density_sum += n_i * n_j_y;
            spin_nn_sum += sz_i * sz_j_y
                         + std::complex<double>(0.5, 0.0) *
                           (sp_i * sm_j_y + sm_i * sp_j_y);
            ++num_nn_bonds;

            // Two next-nearest-neighbor directions, retained for a generic tp.
            lattice.coor2site({x + 1, y + 1}, 0, site_j, work);
            auto c_up_j_pp = qbasis::opr<std::complex<double>>(site_j, 0, true, c_up);
            auto c_dn_j_pp = qbasis::opr<std::complex<double>>(site_j, 0, true, c_dn);
            auto c_up_dg_j_pp = c_up_j_pp;
            auto c_dn_dg_j_pp = c_dn_j_pp;
            c_up_dg_j_pp.dagger();
            c_dn_dg_j_pp.dagger();
            auto hop_up_pp_f = std::complex<double>(-tp * cxpy, -tp * sxpy) *
                               (c_up_dg_i * c_up_j_pp);
            auto hop_up_pp_b = std::complex<double>(-tp * cxpy, tp * sxpy) *
                               (c_up_dg_j_pp * c_up_i);
            auto hop_dn_pp_f = std::complex<double>(-tp * cxpy, -tp * sxpy) *
                               (c_dn_dg_i * c_dn_j_pp);
            auto hop_dn_pp_b = std::complex<double>(-tp * cxpy, tp * sxpy) *
                               (c_dn_dg_j_pp * c_dn_i);
            Hubbard.add_Ham(hop_up_pp_f);
            Hubbard.add_Ham(hop_up_pp_b);
            Hubbard.add_Ham(hop_dn_pp_f);
            Hubbard.add_Ham(hop_dn_pp_b);
            kinetic_nnn += hop_up_pp_f + hop_up_pp_b + hop_dn_pp_f + hop_dn_pp_b;

            lattice.coor2site({x + 1, y - 1}, 0, site_j, work);
            auto c_up_j_pm = qbasis::opr<std::complex<double>>(site_j, 0, true, c_up);
            auto c_dn_j_pm = qbasis::opr<std::complex<double>>(site_j, 0, true, c_dn);
            auto c_up_dg_j_pm = c_up_j_pm;
            auto c_dn_dg_j_pm = c_dn_j_pm;
            c_up_dg_j_pm.dagger();
            c_dn_dg_j_pm.dagger();
            auto hop_up_pm_f = std::complex<double>(-tp * cxmy, -tp * sxmy) *
                               (c_up_dg_i * c_up_j_pm);
            auto hop_up_pm_b = std::complex<double>(-tp * cxmy, tp * sxmy) *
                               (c_up_dg_j_pm * c_up_i);
            auto hop_dn_pm_f = std::complex<double>(-tp * cxmy, -tp * sxmy) *
                               (c_dn_dg_i * c_dn_j_pm);
            auto hop_dn_pm_b = std::complex<double>(-tp * cxmy, tp * sxmy) *
                               (c_dn_dg_j_pm * c_dn_i);
            Hubbard.add_Ham(hop_up_pm_f);
            Hubbard.add_Ham(hop_up_pm_b);
            Hubbard.add_Ham(hop_dn_pm_f);
            Hubbard.add_Ham(hop_dn_pm_b);
            kinetic_nnn += hop_up_pm_f + hop_up_pm_b + hop_dn_pm_f + hop_dn_pm_b;

            Hubbard.add_Ham(std::complex<double>(U, 0.0) * (n_up_i * n_dn_i));
        }
    }

    Nup.simplify();
    Ndown.simplify();
    double_occupancy_sum.simplify();
    nn_density_sum.simplify();
    spin_nn_sum.simplify();
    kinetic_nn.simplify();
    kinetic_nnn.simplify();
    charge_pipi.simplify();
    spinz_pipi.simplify();
    c_up_q0.simplify();
    c_dn_q0.simplify();

    auto kinetic_total = kinetic_nn + kinetic_nnn;
    kinetic_total.simplify();
    auto charge_corr_pipi = charge_pipi * charge_pipi;
    auto spinz_corr_pipi = spinz_pipi * spinz_pipi;
    charge_corr_pipi.simplify();
    spinz_corr_pipi.simplify();

    auto c_up_dg_q0 = c_up_q0;
    auto c_dn_dg_q0 = c_dn_q0;
    c_up_dg_q0.dagger();
    c_dn_dg_q0.dagger();
    auto n_up_q0 = c_up_dg_q0 * c_up_q0;
    auto n_dn_q0 = c_dn_dg_q0 * c_dn_q0;
    auto n_q0 = n_up_q0 + n_dn_q0;
    auto double_q0 = n_up_q0 * n_dn_q0;
    n_up_q0.simplify();
    n_dn_q0.simplify();
    n_q0.simplify();
    double_q0.simplify();

    // Full ED: only N_up and N_down are conserved.
    Hubbard.enumerate_basis_full({Nup, Ndown}, {Nup_total, Ndn_total});
    Hubbard.generate_Ham_sparse_full();
    Hubbard.locate_E0_lanczos(qbasis::which_sym::full);

    auto direct = [&](qbasis::mopr<std::complex<double>>& op) {
        return Hubbard.measure_full_static(op, 0, 0);
    };

    auto Ntotal_op = Nup + Ndown;
    Ntotal_op.simplify();
    std::vector<std::complex<double>> vec_number(Hubbard.dim_full[0]);
    Hubbard.moprXvec_full(Ntotal_op, 0, 0, static_cast<MKL_INT>(0), vec_number.data());

    // This duplicates the fixed-N reference-vector estimator used by the
    // momentum-resolved calculation and compares it with direct full-ED values.
    auto fixedN_reference = [&](qbasis::mopr<std::complex<double>>& op) {
        std::vector<std::complex<double>> vec_op(Hubbard.dim_full[0]);
        Hubbard.moprXvec_full(op, 0, 0, static_cast<MKL_INT>(0), vec_op.data());
        std::complex<double> value = 0.0;
        for (MKL_INT i = 0; i < Hubbard.dim_full[0]; ++i) {
            value += std::conj(vec_number[i]) * vec_op[i];
        }
        return value / Ntotal;
    };

    auto norm2_same_sector = [&](qbasis::mopr<std::complex<double>>& op) {
        std::vector<std::complex<double>> vec_op(Hubbard.dim_full[0]);
        Hubbard.moprXvec_full(op, 0, 0, static_cast<MKL_INT>(0), vec_op.data());
        double value = 0.0;
        for (const auto& z : vec_op) value += std::norm(z);
        return value;
    };

    const auto D_sum_direct = direct(double_occupancy_sum);
    const auto D_sum_reference = fixedN_reference(double_occupancy_sum);
    const auto nn_sum_direct = direct(nn_density_sum);
    const auto nn_sum_reference = fixedN_reference(nn_density_sum);
    const auto C1_sum_direct = direct(spin_nn_sum);
    const auto C1_sum_reference = fixedN_reference(spin_nn_sum);
    const auto kinetic_nn_direct = direct(kinetic_nn);
    const auto kinetic_nn_reference = fixedN_reference(kinetic_nn);
    const auto kinetic_nnn_direct = direct(kinetic_nnn);
    const auto kinetic_nnn_reference = fixedN_reference(kinetic_nnn);
    const auto kinetic_direct = direct(kinetic_total);
    const auto kinetic_reference = fixedN_reference(kinetic_total);
    const auto Sc_direct = direct(charge_corr_pipi);
    const auto Szz_direct = direct(spinz_corr_pipi);
    const double Sc_norm = norm2_same_sector(charge_pipi);
    const double Szz_norm = norm2_same_sector(spinz_pipi);
    const auto nq_direct = direct(n_q0);
    const auto double_q_direct = direct(double_q0);

    // Independently obtain n(q=0) as ||c_q|psi>||^2, as in the production code.
    Hubbard.enumerate_basis_full(
        {Nup, Ndown}, {Nup_total - 1.0, Ndn_total}, 1
    );
    Hubbard.enumerate_basis_full(
        {Nup, Ndown}, {Nup_total, Ndn_total - 1.0}, 2
    );
    std::vector<std::complex<double>> vec_cup(Hubbard.dim_full[1]);
    std::vector<std::complex<double>> vec_cdn(Hubbard.dim_full[2]);
    Hubbard.moprXvec_full(c_up_q0, 0, 1, static_cast<MKL_INT>(0), vec_cup.data());
    Hubbard.moprXvec_full(c_dn_q0, 0, 2, static_cast<MKL_INT>(0), vec_cdn.data());
    double nq_norm = 0.0;
    for (const auto& z : vec_cup) nq_norm += std::norm(z);
    for (const auto& z : vec_cdn) nq_norm += std::norm(z);

    const double E0 = Hubbard.eigenvals_full[0];
    const double energy_reconstructed = std::real(kinetic_direct)
                                      + U * std::real(D_sum_direct)
                                      + V * std::real(nn_sum_direct);
    const double energy_residual = energy_reconstructed - E0;

    const double D_direct = std::real(D_sum_direct) / Nsites;
    const double D_reference = std::real(D_sum_reference) / Nsites;
    const double nn_direct = std::real(nn_sum_direct) / num_nn_bonds;
    const double nn_reference = std::real(nn_sum_reference) / num_nn_bonds;
    const double C1_direct = std::real(C1_sum_direct) / num_nn_bonds;
    const double C1_reference = std::real(C1_sum_reference) / num_nn_bonds;
    const double K_nn_direct = std::real(kinetic_nn_direct) / Nsites;
    const double K_nn_reference = std::real(kinetic_nn_reference) / Nsites;
    const double K_nnn_direct = std::real(kinetic_nnn_direct) / Nsites;
    const double K_nnn_reference = std::real(kinetic_nnn_reference) / Nsites;
    const double K_direct = std::real(kinetic_direct) / Nsites;
    const double K_reference = std::real(kinetic_reference) / Nsites;

    const double max_direct_reference_difference = std::max({
        std::abs(D_direct - D_reference),
        std::abs(nn_direct - nn_reference),
        std::abs(C1_direct - C1_reference),
        std::abs(K_nn_direct - K_nn_reference),
        std::abs(K_nnn_direct - K_nnn_reference),
        std::abs(K_direct - K_reference)
    });
    const double max_norm_difference = std::max({
        std::abs(std::real(Sc_direct) - Sc_norm),
        std::abs(std::real(Szz_direct) - Szz_norm),
        std::abs(std::real(nq_direct) - nq_norm)
    });
    const double max_imaginary_part = std::max({
        std::abs(std::imag(D_sum_direct)),
        std::abs(std::imag(nn_sum_direct)),
        std::abs(std::imag(C1_sum_direct)),
        std::abs(std::imag(kinetic_direct)),
        std::abs(std::imag(Sc_direct)),
        std::abs(std::imag(Szz_direct)),
        std::abs(std::imag(nq_direct)),
        std::abs(std::imag(double_q_direct))
    });

    const bool pass = std::abs(energy_residual) < 1.0e-9
                   && max_direct_reference_difference < 1.0e-10
                   && max_norm_difference < 1.0e-10
                   && max_imaginary_part < 1.0e-10;

    std::ofstream fout(output_name, std::ios::out);
    fout << std::scientific << std::setprecision(18);
    fout << "Lx " << Lx << '\n';
    fout << "Ly " << Ly << '\n';
    fout << "Nup " << Nup_total << '\n';
    fout << "Ndn " << Ndn_total << '\n';
    fout << "total_momentum_restricted 0\n";
    fout << "U " << U << '\n';
    fout << "V " << V << '\n';
    fout << "tp " << tp << '\n';
    fout << "phi_x " << phi_x << '\n';
    fout << "phi_y " << phi_y << '\n';
    fout << "dim_full " << Hubbard.dim_full[0] << '\n';
    fout << "num_nn_bonds " << num_nn_bonds << '\n';
    fout << "E0 " << E0 << '\n';
    fout << "energy_reconstructed " << energy_reconstructed << '\n';
    fout << "energy_residual " << energy_residual << '\n';
    fout << "D_direct " << D_direct << '\n';
    fout << "D_fixedN_reference " << D_reference << '\n';
    fout << "nn_NN_direct " << nn_direct << '\n';
    fout << "nn_NN_fixedN_reference " << nn_reference << '\n';
    fout << "delta_n_delta_n_NN " << nn_direct - density * density << '\n';
    fout << "Kinetic_NN_per_site_direct " << K_nn_direct << '\n';
    fout << "Kinetic_NN_per_site_fixedN_reference " << K_nn_reference << '\n';
    fout << "Kinetic_NNN_per_site_direct " << K_nnn_direct << '\n';
    fout << "Kinetic_NNN_per_site_fixedN_reference " << K_nnn_reference << '\n';
    fout << "Kinetic_per_site_direct " << K_direct << '\n';
    fout << "Kinetic_per_site_fixedN_reference " << K_reference << '\n';
    fout << "C1_NN_direct " << C1_direct << '\n';
    fout << "C1_NN_fixedN_reference " << C1_reference << '\n';
    fout << "Sc_pipi_direct " << std::real(Sc_direct) << '\n';
    fout << "Sc_pipi_norm " << Sc_norm << '\n';
    fout << "mCDW2_pipi " << std::real(Sc_direct) / Nsites << '\n';
    fout << "Szz_pipi_direct " << std::real(Szz_direct) << '\n';
    fout << "Szz_pipi_norm " << Szz_norm << '\n';
    fout << "nq0_direct " << std::real(nq_direct) << '\n';
    fout << "nq0_norm " << nq_norm << '\n';
    fout << "nq0_upnq0_dn " << std::real(double_q_direct) << '\n';
    fout << "max_direct_reference_difference "
         << max_direct_reference_difference << '\n';
    fout << "max_norm_difference " << max_norm_difference << '\n';
    fout << "max_imaginary_part " << max_imaginary_part << '\n';
    fout << "status " << (pass ? "PASS" : "FAIL") << '\n';
    fout.close();

    std::cout << "4x2 full-ED observable check: "
              << (pass ? "PASS" : "FAIL") << std::endl;
    std::cout << "Output: " << output_name << std::endl;
    std::cout << "E0 = " << E0
              << ", energy residual = " << energy_residual << std::endl;
    std::cout << "max direct/reference difference = "
              << max_direct_reference_difference << std::endl;
    std::cout << "max direct/norm difference = "
              << max_norm_difference << std::endl;

    return pass ? 0 : 2;
}
