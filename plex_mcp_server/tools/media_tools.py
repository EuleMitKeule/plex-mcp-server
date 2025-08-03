"""
Media-related tools for Plex Media Server.
Provides tools to search, get details, edit metadata, and manage media items.
"""

import base64
import json
import os
from typing import List, Optional
from urllib.parse import urlencode

import requests
from mcp.types import AnyFunction
from plexapi.exceptions import NotFound

from plex_mcp_server.const import PermissionsType
from plex_mcp_server.tools.tools import PlexMcpTools


class PlexMediaTools(PlexMcpTools):
    """Tools for managing Plex media items."""

    def __init__(
        self,
        plex_url: str,
        plex_token: str,
        permissions: PermissionsType,
    ) -> None:
        """Initialize the Plex Media Tools."""
        tools: list[AnyFunction] = [
            self.media_search,
            self.media_get_details,
            self.media_get_artwork,
            self.media_list_available_artwork,
        ]
        if permissions in [PermissionsType.WRITE, PermissionsType.DELETE]:
            tools.extend(
                [
                    self.media_edit_metadata,
                    self.media_set_artwork,
                ]
            )
        if permissions == PermissionsType.DELETE:
            tools.append(self.media_delete)

        super().__init__(plex_url, plex_token, permissions, tools)

    async def media_search(self, query: str, content_type: Optional[str] = None) -> str:
        """Search for media across all libraries.

        Args:
            query: Search term to look for
            content_type: Optional content type to limit search to (movie, show, episode, track, album, artist or use comma-separated values for HTTP API like movies,music,tv)
        """
        try:
            # Prepare the search query parameters
            params = {
                "query": query,
                "X-Plex-Token": self._plex_token,
                "limit": 100,  # Ensure we get a good number of results
                "includeCollections": 1,
                "includeExternalMedia": 1,
            }

            # Add content type filter depending on the value provided
            if content_type:
                # Map content_type to searchTypes parameter if needed
                content_type_map = {
                    "movie": "movies",
                    "show": "tv",
                    "episode": "tv",
                    "track": "music",
                    "album": "music",
                    "artist": "music",
                }

                # If it contains a comma, it's already in searchTypes format
                if "," in content_type:
                    params["searchTypes"] = content_type
                elif content_type in content_type_map:
                    # Use searchTypes for better results
                    params["searchTypes"] = content_type_map[content_type]
                    # Also add the specific type filter for more precise filtering
                    params["type"] = content_type
                else:
                    # Just use the provided type directly
                    params["type"] = content_type

            # Add headers for JSON response
            headers = {"Accept": "application/json"}

            # Construct the URL
            search_url = f"{self._plex_url}/library/search?{urlencode(params)}"

            # Make the request
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            # For consistency, return in the same format as before but using the direct HTTP response
            if "MediaContainer" not in data or "SearchResult" not in data.get(
                "MediaContainer", {}
            ):
                return json.dumps(
                    {
                        "status": "success",
                        "message": f"No results found for '{query}'.",
                        "count": 0,
                        "results": [],
                    }
                )

            # Format and organize search results
            results_by_type = {}
            total_count = 0

            for search_result in data["MediaContainer"]["SearchResult"]:
                if "Metadata" not in search_result:
                    continue

                item = search_result["Metadata"]
                item_type = item.get("type", "unknown")

                # Apply additional filter only when content_type is specified and not comma-separated
                # This is to ensure we only return the exact type the user asked for
                if (
                    content_type
                    and "," not in content_type
                    and content_type not in content_type_map
                ):
                    if item_type != content_type:
                        continue

                # When specific content_type is requested but internal mapping is used,
                # ensure we only return that specific type
                if (
                    content_type
                    and content_type in content_type_map
                    and "," not in content_type
                ):
                    if content_type != item_type:
                        continue

                if item_type not in results_by_type:
                    results_by_type[item_type] = []

                # Extract relevant information based on item type
                formatted_item = {
                    "title": item.get("title", "Unknown"),
                    "type": item_type,
                    "rating_key": item.get("ratingKey"),
                }

                if item_type == "movie":
                    formatted_item["year"] = item.get("year")
                    formatted_item["rating"] = item.get("rating")
                    formatted_item["summary"] = item.get("summary")

                elif item_type == "show":
                    formatted_item["year"] = item.get("year")
                    formatted_item["summary"] = item.get("summary")

                elif item_type == "season":
                    formatted_item["show_title"] = item.get(
                        "parentTitle", "Unknown Show"
                    )
                    formatted_item["season_number"] = item.get("index")

                elif item_type == "episode":
                    formatted_item["show_title"] = item.get(
                        "grandparentTitle", "Unknown Show"
                    )
                    formatted_item["season_number"] = item.get("parentIndex")
                    formatted_item["episode_number"] = item.get("index")

                elif item_type == "track":
                    formatted_item["artist"] = item.get(
                        "grandparentTitle", "Unknown Artist"
                    )
                    formatted_item["album"] = item.get("parentTitle", "Unknown Album")
                    formatted_item["track_number"] = item.get("index")
                    formatted_item["duration"] = item.get("duration")
                    formatted_item["library"] = item.get("librarySectionTitle")

                elif item_type == "album":
                    formatted_item["artist"] = item.get("parentTitle", "Unknown Artist")
                    formatted_item["year"] = item.get("parentYear")
                    formatted_item["library"] = item.get("librarySectionTitle")

                elif item_type == "artist":
                    formatted_item["art"] = item.get("art")
                    formatted_item["thumb"] = item.get("thumb")
                    formatted_item["library"] = item.get("librarySectionTitle")

                # Add any media info if available
                if "Media" in item:
                    media_info = (
                        item["Media"][0]
                        if isinstance(item["Media"], list) and item["Media"]
                        else item["Media"]
                    )
                    if isinstance(media_info, dict):
                        if item_type in ["movie", "show", "episode"]:
                            formatted_item["resolution"] = media_info.get(
                                "videoResolution"
                            )
                            formatted_item["container"] = media_info.get("container")
                            formatted_item["codec"] = media_info.get("videoCodec")
                        elif item_type in ["track"]:
                            formatted_item["audio_codec"] = media_info.get("audioCodec")
                            formatted_item["bitrate"] = media_info.get("bitrate")
                            formatted_item["container"] = media_info.get("container")

                # Add thumbnail/artwork info
                if item_type == "track":
                    if "thumb" in item:
                        formatted_item["thumb"] = item.get("thumb")
                    if "parentThumb" in item:
                        formatted_item["album_thumb"] = item.get("parentThumb")
                    if "grandparentThumb" in item:
                        formatted_item["artist_thumb"] = item.get("grandparentThumb")
                    if "art" in item:
                        formatted_item["art"] = item.get("art")

                results_by_type[item_type].append(formatted_item)
                total_count += 1

            # For cleaner display, organize by type
            type_order = [
                "track",
                "album",
                "artist",
                "movie",
                "show",
                "season",
                "episode",
            ]
            ordered_results = {}
            for type_name in type_order:
                if type_name in results_by_type:
                    ordered_results[type_name] = results_by_type[type_name]

            # Add any remaining types
            for type_name in results_by_type:
                if type_name not in ordered_results:
                    ordered_results[type_name] = results_by_type[type_name]

            return json.dumps(
                {
                    "status": "success",
                    "message": f"Found {total_count} results for '{query}'",
                    "query": query,
                    "content_type": content_type,
                    "total_count": total_count,
                    "results_by_type": ordered_results,
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps(
                {"status": "error", "message": f"Error searching for media: {str(e)}"}
            )

    async def media_get_details(
        self,
        media_title: Optional[str] = None,
        media_id: Optional[int] = None,
        library_name: Optional[str] = None,
    ) -> str:
        """Get detailed information about a specific media item.

        Args:
            media_title: Title of the media to get details for (optional if media_id is provided)
            media_id: ID of the media to get details for (optional if media_title is provided)
            library_name: Name of the library to search in (optional if media_id is provided)
        """
        try:
            plex = self._plex_client.connection

            # Validate that at least one identifier is provided
            if not media_id and not media_title:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "Either media_id or media_title must be provided",
                    }
                )

            media = None

            # If media_id is provided, fetch directly
            if media_id:
                try:
                    media = plex.fetchItem(media_id)
                except Exception:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Media with ID '{media_id}' not found",
                        }
                    )
            else:
                # Search by title
                if library_name:
                    try:
                        library = plex.library.section(library_name)
                        results = library.search(title=media_title)
                    except NotFound:
                        return json.dumps(
                            {
                                "status": "error",
                                "message": f"Library '{library_name}' not found",
                            }
                        )
                else:
                    results = plex.search(media_title)

                if not results:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"No media found matching '{media_title}'",
                        }
                    )

                # If multiple results, provide information about them
                if len(results) > 1:
                    media_list = []
                    for i, item in enumerate(results[:10], 1):  # Limit to first 10
                        media_type = getattr(item, "type", "unknown")
                        title = getattr(item, "title", "Unknown")
                        year = getattr(item, "year", "")

                        media_info = {
                            "index": i,
                            "title": title,
                            "type": media_type,
                            "rating_key": getattr(item, "ratingKey", None),
                        }

                        if year:
                            media_info["year"] = year

                        if media_type == "episode":
                            show = getattr(item, "grandparentTitle", "Unknown Show")
                            season = getattr(item, "parentIndex", "?")
                            episode = getattr(item, "index", "?")
                            media_info["show"] = show
                            media_info["season"] = season
                            media_info["episode"] = episode

                        media_list.append(media_info)

                    return json.dumps(
                        {
                            "status": "multiple_results",
                            "message": f"Multiple items found matching '{media_title}'. Please specify a media_id or use a more specific title.",
                            "count": len(results),
                            "results": media_list,
                        },
                        indent=2,
                    )

                media = results[0]

            # Extract detailed information
            details = {
                "title": getattr(media, "title", "Unknown"),
                "type": getattr(media, "type", "unknown"),
                "rating_key": getattr(media, "ratingKey", None),
                "summary": getattr(media, "summary", ""),
                "year": getattr(media, "year", None),
                "added_at": str(getattr(media, "addedAt", "")),
                "updated_at": str(getattr(media, "updatedAt", "")),
                "duration": getattr(media, "duration", None),
                "view_count": getattr(media, "viewCount", 0),
                "last_viewed_at": str(getattr(media, "lastViewedAt", ""))
                if getattr(media, "lastViewedAt", None)
                else None,
            }

            # Add type-specific information
            media_type = getattr(media, "type", "unknown")

            if media_type == "movie":
                details.update(
                    {
                        "content_rating": getattr(media, "contentRating", ""),
                        "rating": getattr(media, "rating", None),
                        "studio": getattr(media, "studio", ""),
                        "tagline": getattr(media, "tagline", ""),
                        "directors": [d.tag for d in getattr(media, "directors", [])],
                        "writers": [w.tag for w in getattr(media, "writers", [])],
                        "actors": [
                            {"name": a.tag, "role": getattr(a, "role", "")}
                            for a in getattr(media, "roles", [])[:10]
                        ],
                        "genres": [g.tag for g in getattr(media, "genres", [])],
                        "countries": [c.tag for c in getattr(media, "countries", [])],
                    }
                )

            elif media_type == "show":
                details.update(
                    {
                        "content_rating": getattr(media, "contentRating", ""),
                        "rating": getattr(media, "rating", None),
                        "studio": getattr(media, "studio", ""),
                        "season_count": getattr(media, "childCount", 0),
                        "episode_count": getattr(media, "leafCount", 0),
                        "viewed_episode_count": getattr(media, "viewedLeafCount", 0),
                        "genres": [g.tag for g in getattr(media, "genres", [])],
                        "actors": [
                            {"name": a.tag, "role": getattr(a, "role", "")}
                            for a in getattr(media, "roles", [])[:10]
                        ],
                    }
                )

            elif media_type == "episode":
                details.update(
                    {
                        "show_title": getattr(
                            media, "grandparentTitle", "Unknown Show"
                        ),
                        "season_title": getattr(media, "parentTitle", "Unknown Season"),
                        "season_number": getattr(media, "parentIndex", None),
                        "episode_number": getattr(media, "index", None),
                        "content_rating": getattr(media, "contentRating", ""),
                        "rating": getattr(media, "rating", None),
                        "directors": [d.tag for d in getattr(media, "directors", [])],
                        "writers": [w.tag for w in getattr(media, "writers", [])],
                    }
                )

            elif media_type == "track":
                details.update(
                    {
                        "artist": getattr(media, "grandparentTitle", "Unknown Artist"),
                        "album": getattr(media, "parentTitle", "Unknown Album"),
                        "track_number": getattr(media, "index", None),
                        "disc_number": getattr(media, "parentIndex", None),
                        "skip_count": getattr(media, "skipCount", 0),
                        "play_count": getattr(media, "viewCount", 0),
                    }
                )

            elif media_type == "album":
                details.update(
                    {
                        "artist": getattr(media, "parentTitle", "Unknown Artist"),
                        "track_count": getattr(media, "leafCount", 0),
                        "genres": [g.tag for g in getattr(media, "genres", [])],
                    }
                )

            elif media_type == "artist":
                details.update(
                    {
                        "album_count": getattr(media, "childCount", 0),
                        "track_count": getattr(media, "leafCount", 0),
                        "genres": [g.tag for g in getattr(media, "genres", [])],
                        "similar_artists": [
                            a.tag for a in getattr(media, "similar", [])
                        ],
                    }
                )

            # Add media file information
            if hasattr(media, "media") and media.media:
                media_files = []
                for media_item in media.media:
                    media_info = {
                        "id": getattr(media_item, "id", None),
                        "duration": getattr(media_item, "duration", None),
                        "bitrate": getattr(media_item, "bitrate", None),
                        "container": getattr(media_item, "container", ""),
                        "size": getattr(media_item, "size", None),
                    }

                    # Add video/audio specific info
                    if media_type in ["movie", "show", "episode"]:
                        media_info.update(
                            {
                                "video_codec": getattr(media_item, "videoCodec", ""),
                                "video_resolution": getattr(
                                    media_item, "videoResolution", ""
                                ),
                                "video_frame_rate": getattr(
                                    media_item, "videoFrameRate", ""
                                ),
                                "aspect_ratio": getattr(
                                    media_item, "aspectRatio", None
                                ),
                                "audio_codec": getattr(media_item, "audioCodec", ""),
                                "audio_channels": getattr(
                                    media_item, "audioChannels", None
                                ),
                            }
                        )
                    elif media_type == "track":
                        media_info.update(
                            {
                                "audio_codec": getattr(media_item, "audioCodec", ""),
                                "audio_channels": getattr(
                                    media_item, "audioChannels", None
                                ),
                                "sample_rate": getattr(
                                    media_item, "audioSampleRate", None
                                ),
                            }
                        )

                    # Add file parts
                    if hasattr(media_item, "parts") and media_item.parts:
                        parts = []
                        for part in media_item.parts:
                            part_info = {
                                "id": getattr(part, "id", None),
                                "file": getattr(part, "file", ""),
                                "size": getattr(part, "size", None),
                                "duration": getattr(part, "duration", None),
                                "container": getattr(part, "container", ""),
                            }
                            parts.append(part_info)
                        media_info["parts"] = parts

                    media_files.append(media_info)

                details["media_files"] = media_files

            return json.dumps({"status": "success", "details": details}, indent=2)

        except Exception as e:
            return json.dumps(
                {"status": "error", "message": f"Error getting media details: {str(e)}"}
            )

    async def media_edit_metadata(
        self,
        media_title: str,
        library_name: Optional[str] = None,
        new_title: Optional[str] = None,
        new_summary: Optional[str] = None,
        new_year: Optional[int] = None,
        new_rating: Optional[float] = None,
        new_content_rating: Optional[str] = None,
        new_studio: Optional[str] = None,
        new_tagline: Optional[str] = None,
        new_sort_title: Optional[str] = None,
        new_original_title: Optional[str] = None,
        new_genres: Optional[List[str]] = None,
        add_genres: Optional[List[str]] = None,
        remove_genres: Optional[List[str]] = None,
        new_labels: Optional[List[str]] = None,
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None,
    ) -> str:
        """Edit metadata for a media item.

        Args:
            media_title: Title of the media to edit
            library_name: Name of the library containing the media
            new_title: New title for the media
            new_summary: New summary/description
            new_year: New release year
            new_rating: New rating (0-10)
            new_content_rating: New content rating (e.g., PG-13, R, etc.)
            new_studio: New studio
            new_tagline: New tagline
            new_sort_title: New sort title
            new_original_title: New original title
            new_genres: Set completely new genres (replaces existing)
            add_genres: Genres to add to existing ones
            remove_genres: Genres to remove from existing ones
            new_labels: Set completely new labels (replaces existing)
            add_labels: Labels to add to existing ones
            remove_labels: Labels to remove from existing ones
        """
        try:
            plex = self._plex_client.connection

            # Find the media item
            if library_name:
                try:
                    library = plex.library.section(library_name)
                    results = library.search(title=media_title)
                except NotFound:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Library '{library_name}' not found",
                        }
                    )
            else:
                results = plex.search(media_title)

            if not results:
                return json.dumps(
                    {
                        "status": "error",
                        "message": f"No media found matching '{media_title}'",
                    }
                )

            if len(results) > 1:
                # Multiple results found, show them
                media_list = []
                for i, item in enumerate(results[:10], 1):
                    media_type = getattr(item, "type", "unknown")
                    title = getattr(item, "title", "Unknown")
                    year = getattr(item, "year", "")

                    media_info = {
                        "index": i,
                        "title": title,
                        "type": media_type,
                        "rating_key": getattr(item, "ratingKey", None),
                    }

                    if year:
                        media_info["year"] = year

                    media_list.append(media_info)

                return json.dumps(
                    {
                        "status": "multiple_results",
                        "message": f"Multiple items found matching '{media_title}'. Please be more specific or use media_id.",
                        "count": len(results),
                        "results": media_list,
                    },
                    indent=2,
                )

            media = results[0]
            changes = []

            # Edit basic attributes
            edit_params = {}

            if new_title is not None and new_title != media.title:
                edit_params["title"] = new_title
                changes.append(f"title to '{new_title}'")

            if new_summary is not None:
                current_summary = getattr(media, "summary", "")
                if new_summary != current_summary:
                    edit_params["summary"] = new_summary
                    changes.append("summary")

            if new_year is not None:
                current_year = getattr(media, "year", None)
                if new_year != current_year:
                    edit_params["year"] = new_year
                    changes.append(f"year to {new_year}")

            if new_rating is not None:
                current_rating = getattr(media, "rating", None)
                if new_rating != current_rating:
                    edit_params["rating"] = new_rating
                    changes.append(f"rating to {new_rating}")

            if new_content_rating is not None:
                current_content_rating = getattr(media, "contentRating", "")
                if new_content_rating != current_content_rating:
                    edit_params["contentRating"] = new_content_rating
                    changes.append(f"content rating to '{new_content_rating}'")

            if new_studio is not None:
                current_studio = getattr(media, "studio", "")
                if new_studio != current_studio:
                    edit_params["studio"] = new_studio
                    changes.append(f"studio to '{new_studio}'")

            if new_tagline is not None:
                current_tagline = getattr(media, "tagline", "")
                if new_tagline != current_tagline:
                    edit_params["tagline"] = new_tagline
                    changes.append("tagline")

            if new_sort_title is not None:
                current_sort_title = getattr(media, "titleSort", "")
                if new_sort_title != current_sort_title:
                    edit_params["titleSort"] = new_sort_title
                    changes.append(f"sort title to '{new_sort_title}'")

            if new_original_title is not None:
                current_original_title = getattr(media, "originalTitle", "")
                if new_original_title != current_original_title:
                    edit_params["originalTitle"] = new_original_title
                    changes.append(f"original title to '{new_original_title}'")

            # Apply the basic edits if any parameters were set
            if edit_params:
                media.edit(**edit_params)

            # Handle genres
            current_genres = [g.tag for g in getattr(media, "genres", [])]

            if new_genres is not None:
                # Replace all genres
                media.removeGenre(current_genres)
                if new_genres:
                    media.addGenre(new_genres)
                changes.append("genres completely replaced")
            else:
                # Handle adding and removing individual genres
                if add_genres:
                    for genre in add_genres:
                        if genre not in current_genres:
                            media.addGenre(genre)
                    changes.append(f"added genres: {', '.join(add_genres)}")

                if remove_genres:
                    for genre in remove_genres:
                        if genre in current_genres:
                            media.removeGenre(genre)
                    changes.append(f"removed genres: {', '.join(remove_genres)}")

            # Handle labels
            current_labels = [label.tag for label in getattr(media, "labels", [])]

            if new_labels is not None:
                # Replace all labels
                media.removeLabel(current_labels)
                if new_labels:
                    media.addLabel(new_labels)
                changes.append("labels completely replaced")
            else:
                # Handle adding and removing individual labels
                if add_labels:
                    for label in add_labels:
                        if label not in current_labels:
                            media.addLabel(label)
                    changes.append(f"added labels: {', '.join(add_labels)}")

                if remove_labels:
                    for label in remove_labels:
                        if label in current_labels:
                            media.removeLabel(label)
                    changes.append(f"removed labels: {', '.join(remove_labels)}")

            if not changes:
                return json.dumps(
                    {
                        "status": "no_changes",
                        "message": "No changes made to the media item",
                    }
                )

            return json.dumps(
                {
                    "status": "success",
                    "message": f"Successfully updated '{media.title}'",
                    "changes": changes,
                    "title": media.title,
                    "type": getattr(media, "type", "unknown"),
                },
                indent=2,
            )

        except Exception as e:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Error editing media metadata: {str(e)}",
                }
            )

    async def media_get_artwork(
        self,
        media_title: Optional[str] = None,
        media_id: Optional[int] = None,
        library_name: Optional[str] = None,
        art_type: str = "poster",
        save_to_file: bool = False,
        output_path: Optional[str] = None,
    ) -> str:
        """Get artwork (poster/background) for a media item.

        Args:
            media_title: Title of the media to get artwork for (optional if media_id is provided)
            media_id: ID of the media to get artwork for (optional if media_title is provided)
            library_name: Name of the library to search in (optional if media_id is provided)
            art_type: Type of artwork to get ('poster' or 'art'/'background')
            save_to_file: Whether to save the image to a file
            output_path: Path to save the image file (if save_to_file is True)
        """
        try:
            plex = self._plex_client.connection

            # Validate that at least one identifier is provided
            if not media_id and not media_title:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "Either media_id or media_title must be provided",
                    }
                )

            # Validate art_type
            if art_type not in ["poster", "art", "background"]:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "art_type must be 'poster', 'art', or 'background'",
                    }
                )

            media = None

            # Find the media item
            if media_id:
                try:
                    media = plex.fetchItem(media_id)
                except Exception:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Media with ID '{media_id}' not found",
                        }
                    )
            else:
                # Search by title
                if library_name:
                    try:
                        library = plex.library.section(library_name)
                        results = library.search(title=media_title)
                    except NotFound:
                        return json.dumps(
                            {
                                "status": "error",
                                "message": f"Library '{library_name}' not found",
                            }
                        )
                else:
                    results = plex.search(media_title)

                if not results:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"No media found matching '{media_title}'",
                        }
                    )

                if len(results) > 1:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Multiple items found matching '{media_title}'. Please use media_id for specific selection.",
                        }
                    )

                media = results[0]

            # Get the artwork URL
            artwork_url = None
            if art_type == "poster":
                artwork_url = getattr(media, "thumb", None)
            elif art_type in ["art", "background"]:
                artwork_url = getattr(media, "art", None)

            if not artwork_url:
                return json.dumps(
                    {
                        "status": "error",
                        "message": f"No {art_type} artwork available for this media item",
                    }
                )

            # Construct full URL
            full_url = f"{self._plex_url}{artwork_url}?X-Plex-Token={self._plex_token}"

            if save_to_file:
                # Download and save the image
                import requests

                response = requests.get(full_url)
                response.raise_for_status()

                # Determine file extension from content type
                content_type = response.headers.get("content-type", "")
                if "jpeg" in content_type or "jpg" in content_type:
                    ext = ".jpg"
                elif "png" in content_type:
                    ext = ".png"
                else:
                    ext = ".jpg"  # Default

                # Generate filename if not provided
                if not output_path:
                    safe_title = "".join(
                        c for c in media.title if c.isalnum() or c in (" ", "-", "_")
                    ).strip()
                    output_path = f"{safe_title}_{art_type}{ext}"

                # Save the file
                with open(output_path, "wb") as f:
                    f.write(response.content)

                return json.dumps(
                    {
                        "status": "success",
                        "message": f"Artwork saved to '{output_path}'",
                        "title": media.title,
                        "art_type": art_type,
                        "file_path": output_path,
                        "file_size": len(response.content),
                    }
                )
            else:
                # Return base64 encoded image data
                import requests

                response = requests.get(full_url)
                response.raise_for_status()

                # Encode as base64
                image_data = base64.b64encode(response.content).decode("utf-8")
                content_type = response.headers.get("content-type", "image/jpeg")

                return json.dumps(
                    {
                        "status": "success",
                        "title": media.title,
                        "art_type": art_type,
                        "content_type": content_type,
                        "size": len(response.content),
                        "data": image_data,
                        "url": full_url,
                    }
                )

        except Exception as e:
            return json.dumps(
                {"status": "error", "message": f"Error getting media artwork: {str(e)}"}
            )

    async def media_delete(
        self,
        media_title: Optional[str] = None,
        media_id: Optional[int] = None,
        library_name: Optional[str] = None,
    ) -> str:
        """Delete a media item from Plex (removes from library and deletes files).

        Args:
            media_title: Title of the media to delete (optional if media_id is provided)
            media_id: ID of the media to delete (optional if media_title is provided)
            library_name: Name of the library to search in (optional if media_id is provided)
        """
        try:
            plex = self._plex_client.connection

            # Validate that at least one identifier is provided
            if not media_id and not media_title:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "Either media_id or media_title must be provided",
                    }
                )

            media = None

            # Find the media item
            if media_id:
                try:
                    media = plex.fetchItem(media_id)
                except Exception:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Media with ID '{media_id}' not found",
                        }
                    )
            else:
                # Search by title
                if library_name:
                    try:
                        library = plex.library.section(library_name)
                        results = library.search(title=media_title)
                    except NotFound:
                        return json.dumps(
                            {
                                "status": "error",
                                "message": f"Library '{library_name}' not found",
                            }
                        )
                else:
                    results = plex.search(media_title)

                if not results:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"No media found matching '{media_title}'",
                        }
                    )

                if len(results) > 1:
                    # Multiple results found, show them
                    media_list = []
                    for i, item in enumerate(results[:10], 1):
                        media_type = getattr(item, "type", "unknown")
                        title = getattr(item, "title", "Unknown")
                        year = getattr(item, "year", "")

                        media_info = {
                            "index": i,
                            "title": title,
                            "type": media_type,
                            "rating_key": getattr(item, "ratingKey", None),
                        }

                        if year:
                            media_info["year"] = year

                        media_list.append(media_info)

                    return json.dumps(
                        {
                            "status": "multiple_results",
                            "message": f"Multiple items found matching '{media_title}'. Please be more specific or use media_id.",
                            "count": len(results),
                            "results": media_list,
                        },
                        indent=2,
                    )

                media = results[0]

            # Get some info before deletion
            media_title_for_response = getattr(media, "title", "Unknown")
            media_type = getattr(media, "type", "unknown")

            # Delete the media item
            media.delete()

            return json.dumps(
                {
                    "status": "success",
                    "message": f"Successfully deleted '{media_title_for_response}' ({media_type})",
                    "deleted_title": media_title_for_response,
                    "deleted_type": media_type,
                }
            )

        except Exception as e:
            return json.dumps(
                {"status": "error", "message": f"Error deleting media: {str(e)}"}
            )

    async def media_set_artwork(
        self,
        media_title: str,
        library_name: Optional[str] = None,
        poster_path: Optional[str] = None,
        poster_url: Optional[str] = None,
        background_path: Optional[str] = None,
        background_url: Optional[str] = None,
    ) -> str:
        """Set artwork (poster/background) for a media item.

        Args:
            media_title: Title of the media to set artwork for
            library_name: Name of the library containing the media
            poster_path: Path to a poster image file
            poster_url: URL to a poster image
            background_path: Path to a background/art image file
            background_url: URL to a background/art image
        """
        try:
            plex = self._plex_client.connection

            # Validate that at least one artwork source is provided
            if (
                not poster_path
                and not poster_url
                and not background_path
                and not background_url
            ):
                return json.dumps(
                    {
                        "status": "error",
                        "message": "At least one artwork source must be provided (poster_path, poster_url, background_path, or background_url)",
                    }
                )

            # Find the media item
            if library_name:
                try:
                    library = plex.library.section(library_name)
                    results = library.search(title=media_title)
                except NotFound:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Library '{library_name}' not found",
                        }
                    )
            else:
                results = plex.search(media_title)

            if not results:
                return json.dumps(
                    {
                        "status": "error",
                        "message": f"No media found matching '{media_title}'",
                    }
                )

            if len(results) > 1:
                # Multiple results found, show them
                media_list = []
                for i, item in enumerate(results[:10], 1):
                    media_type = getattr(item, "type", "unknown")
                    title = getattr(item, "title", "Unknown")
                    year = getattr(item, "year", "")

                    media_info = {
                        "index": i,
                        "title": title,
                        "type": media_type,
                        "rating_key": getattr(item, "ratingKey", None),
                    }

                    if year:
                        media_info["year"] = year

                    media_list.append(media_info)

                return json.dumps(
                    {
                        "status": "multiple_results",
                        "message": f"Multiple items found matching '{media_title}'. Please be more specific.",
                        "count": len(results),
                        "results": media_list,
                    },
                    indent=2,
                )

            media = results[0]
            changes = []

            # Set poster artwork
            if poster_path:
                if os.path.exists(poster_path):
                    media.uploadPoster(filepath=poster_path)
                    changes.append("poster (from file)")
                else:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Poster file not found: {poster_path}",
                        }
                    )
            elif poster_url:
                media.uploadPoster(url=poster_url)
                changes.append("poster (from URL)")

            # Set background artwork
            if background_path:
                if os.path.exists(background_path):
                    media.uploadArt(filepath=background_path)
                    changes.append("background art (from file)")
                else:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Background file not found: {background_path}",
                        }
                    )
            elif background_url:
                media.uploadArt(url=background_url)
                changes.append("background art (from URL)")

            return json.dumps(
                {
                    "status": "success",
                    "message": f"Successfully updated artwork for '{media.title}'",
                    "changes": changes,
                    "title": media.title,
                    "type": getattr(media, "type", "unknown"),
                }
            )

        except Exception as e:
            return json.dumps(
                {"status": "error", "message": f"Error setting media artwork: {str(e)}"}
            )

    async def media_list_available_artwork(
        self,
        media_title: Optional[str] = None,
        media_id: Optional[int] = None,
        library_name: Optional[str] = None,
        art_type: str = "poster",
    ) -> str:
        """List available artwork options for a media item.

        Args:
            media_title: Title of the media to list artwork for (optional if media_id is provided)
            media_id: ID of the media to list artwork for (optional if media_title is provided)
            library_name: Name of the library to search in (optional if media_id is provided)
            art_type: Type of artwork to list ('poster' or 'art'/'background')
        """
        try:
            plex = self._plex_client.connection

            # Validate that at least one identifier is provided
            if not media_id and not media_title:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "Either media_id or media_title must be provided",
                    }
                )

            # Validate art_type
            if art_type not in ["poster", "art", "background"]:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "art_type must be 'poster', 'art', or 'background'",
                    }
                )

            media = None

            # Find the media item
            if media_id:
                try:
                    media = plex.fetchItem(media_id)
                except Exception:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Media with ID '{media_id}' not found",
                        }
                    )
            else:
                # Search by title
                if library_name:
                    try:
                        library = plex.library.section(library_name)
                        results = library.search(title=media_title)
                    except NotFound:
                        return json.dumps(
                            {
                                "status": "error",
                                "message": f"Library '{library_name}' not found",
                            }
                        )
                else:
                    results = plex.search(media_title)

                if not results:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"No media found matching '{media_title}'",
                        }
                    )

                if len(results) > 1:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Multiple items found matching '{media_title}'. Please use media_id for specific selection.",
                        }
                    )

                media = results[0]

            # Get available artwork
            available_artwork = []

            # Map art_type to the appropriate method
            if art_type == "poster":
                artwork_items = getattr(media, "posters", lambda: [])()
            elif art_type in ["art", "background"]:
                artwork_items = getattr(media, "arts", lambda: [])()
            else:
                artwork_items = []

            for artwork in artwork_items:
                artwork_info = {
                    "key": getattr(artwork, "key", ""),
                    "ratingKey": getattr(artwork, "ratingKey", ""),
                    "selected": getattr(artwork, "selected", False),
                    "provider": getattr(artwork, "provider", "unknown"),
                }

                # Add thumbnail URL if available
                if hasattr(artwork, "thumb"):
                    artwork_info["thumb_url"] = (
                        f"{self._plex_url}{artwork.thumb}?X-Plex-Token={self._plex_token}"
                    )

                available_artwork.append(artwork_info)

            return json.dumps(
                {
                    "status": "success",
                    "title": getattr(media, "title", "Unknown"),
                    "type": getattr(media, "type", "unknown"),
                    "art_type": art_type,
                    "available_count": len(available_artwork),
                    "available_artwork": available_artwork,
                },
                indent=2,
            )

        except Exception as e:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Error listing available artwork: {str(e)}",
                }
            )
