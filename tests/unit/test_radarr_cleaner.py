"""Test radarr_cleaner utility functions."""

from pathlib import Path

from prompt_mapper.utils.radarr_cleaner import clean_movie_filename, extract_edition_info


class TestCleanMovieFilename:
    """Test clean_movie_filename function."""

    def test_goosebumps_cytsunen_release(self):
        """Test Goosebumps with CyTSuNee release group after codec."""
        filename = "Goosebumps.2015.1080p.BluRay.DTS.X264.CyTSuNee.mkv"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "Goosebumps"
        assert year == 2015

    def test_ghostbusters_frozen_empire(self):
        """Test Ghostbusters Frozen Empire with release group."""
        filename = "Ghostbusters.Frozen.Empire.2024.1080p.BluRay.DTS.x264-CyTSuNee.mkv"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "Ghostbusters Frozen Empire"
        assert year == 2024

    def test_fricke_baraka_with_numbers(self):
        """Test Fricke 2 Baraka - should preserve the '2' as part of title."""
        filename = "Fricke.2.Baraka.1992.1080p.BluRay.DTS.x264-CyTSuNee.mkv"
        clean_name, year = clean_movie_filename(filename)
        # The '2' should be preserved as part of the title
        assert clean_name == "Fricke 2 Baraka"
        assert year == 1992

    def test_basic_format_with_year_and_quality(self):
        """Test basic movie format with year and quality."""
        filename = "The.Matrix.1999.1080p.BluRay.x264-GROUP"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "The Matrix"
        assert year == 1999

    def test_parentheses_year(self):
        """Test movie with year in parentheses."""
        filename = "Inception (2010) [1080p]"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "Inception"
        assert year == 2010

    def test_release_group_after_dash(self):
        """Test release group after dash."""
        filename = "Avatar.2009.1080p.BluRay.x264-SPARKS"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "Avatar"
        assert year == 2009

    def test_release_group_after_dot(self):
        """Test release group after dot (no codec before)."""
        filename = "Titanic.1997.1080p.BluRay.YIFY"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "Titanic"
        assert year == 1997

    def test_multiple_quality_indicators(self):
        """Test filename with multiple quality indicators."""
        filename = "Interstellar.2014.2160p.4K.UHD.BluRay.x265.10bit.HDR.DTS-HD.MA.7.1-GROUP"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "Interstellar"
        assert year == 2014

    def test_no_year(self):
        """Test filename without year."""
        filename = "Unknown.Movie.1080p.BluRay.x264-GROUP"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "Unknown Movie"
        assert year is None

    def test_with_edition(self):
        """Test filename with edition info."""
        filename = "Blade.Runner.1982.Directors.Cut.1080p.BluRay.x264-GROUP"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "Blade Runner"
        assert year == 1982

    def test_extended_edition(self):
        """Test filename with extended edition."""
        filename = "The.Lord.of.the.Rings.2001.Extended.1080p.BluRay.x264-GROUP"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "The Lord of the Rings"
        assert year == 2001

    def test_remux_release(self):
        """Test REMUX release."""
        filename = "Dune.2021.2160p.UHD.BluRay.REMUX.HDR.DTS-HD.MA.5.1.x265-GROUP"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "Dune"
        assert year == 2021

    def test_web_dl_release(self):
        """Test WEB-DL release."""
        filename = "Extraction.2020.1080p.WEB-DL.DD5.1.H264-CMRG"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "Extraction"
        assert year == 2020

    def test_sample_file(self):
        """Test sample file - 'sample' should be removed."""
        filename = "Sample.The.Movie.2020.1080p.BluRay.x264-GROUP"
        clean_name, year = clean_movie_filename(filename)
        assert "sample" not in clean_name.lower()
        assert clean_name == "The Movie"
        assert year == 2020

    def test_path_object_input(self):
        """Test that Path objects are handled correctly."""
        filepath = Path("/movies/The.Matrix.1999.1080p.BluRay.x264-GROUP.mkv")
        clean_name, year = clean_movie_filename(filepath)
        assert clean_name == "The Matrix"
        assert year == 1999

    def test_underscores_instead_of_dots(self):
        """Test filename with underscores instead of dots."""
        filename = "The_Prestige_2006_1080p_BluRay_x264-GROUP"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "The Prestige"
        assert year == 2006

    def test_mixed_dots_and_underscores(self):
        """Test filename with mixed dots and underscores."""
        filename = "The_Dark.Knight.2008.1080p_BluRay.x264-GROUP"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "The Dark Knight"
        assert year == 2008

    def test_hevc_codec(self):
        """Test HEVC/H.265 codec."""
        filename = "Tenet.2020.1080p.BluRay.HEVC.x265.10bit-GROUP"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "Tenet"
        assert year == 2020

    def test_atmos_audio(self):
        """Test Atmos audio track."""
        filename = "Dunkirk.2017.1080p.BluRay.Atmos.TrueHD.7.1.x264-GROUP"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "Dunkirk"
        assert year == 2017

    def test_repack_proper_tags(self):
        """Test REPACK and PROPER tags."""
        filename = "The.Revenant.2015.REPACK.1080p.BluRay.x264-GROUP"
        clean_name, year = clean_movie_filename(filename)
        assert clean_name == "The Revenant"
        assert year == 2015


class TestExtractEditionInfo:
    """Test extract_edition_info function."""

    def test_directors_cut(self):
        """Test Director's Cut detection."""
        assert extract_edition_info("Blade.Runner.Directors.Cut.1080p") == "Director's Cut"
        assert extract_edition_info("Movie.Director's.Cut.2020") == "Director's Cut"

    def test_extended_edition(self):
        """Test Extended edition detection."""
        assert extract_edition_info("LOTR.Extended.Edition.2001") == "Extended"
        assert extract_edition_info("Movie.Extended.Cut.2020") == "Extended"

    def test_unrated(self):
        """Test Unrated edition detection."""
        assert extract_edition_info("Movie.Unrated.2020") == "Unrated"
        assert extract_edition_info("Movie.Unrated.Cut.2020") == "Unrated"

    def test_theatrical(self):
        """Test Theatrical edition detection."""
        assert extract_edition_info("Movie.Theatrical.Cut.2020") == "Theatrical"
        assert extract_edition_info("Movie.Theatrical.2020") == "Theatrical"

    def test_final_cut(self):
        """Test Final Cut detection."""
        assert extract_edition_info("Movie.Final.Cut.2020") == "Final Cut"

    def test_remastered(self):
        """Test Remastered detection."""
        assert extract_edition_info("Movie.Remastered.2020") == "Remastered"

    def test_special_edition(self):
        """Test Special Edition detection."""
        assert extract_edition_info("Movie.Special.Edition.2020") == "Special Edition"

    def test_ultimate_edition(self):
        """Test Ultimate Edition detection."""
        assert extract_edition_info("Movie.Ultimate.Edition.2020") == "Ultimate Edition"

    def test_criterion(self):
        """Test Criterion edition detection."""
        assert extract_edition_info("Movie.Criterion.Collection.2020") == "Criterion"
        assert extract_edition_info("Movie.Criterion.Edition.2020") == "Criterion"

    def test_no_edition(self):
        """Test filename without edition info."""
        assert extract_edition_info("Movie.2020.1080p.BluRay") is None

    def test_case_insensitive(self):
        """Test case insensitive matching."""
        assert extract_edition_info("Movie.DIRECTORS.CUT.2020") == "Director's Cut"
        assert extract_edition_info("movie.extended.edition.2020") == "Extended"
