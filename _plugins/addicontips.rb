module Jekyll
  module IconTipFilter
    @@icons = [
        {c: 'fas fa-book', n: 'closed book', t: 'piece', d: 'is a professionally-published book'},
        {c: 'fas fa-person-chalkboard', n: 'teacher', t: 'course', d: 'is taught by...'},
        {c: 'fas fa-user-slash', n: 'person with a slash through him', t: 'course', d: 'is about selflessness'},
        {c: 'far fa-address-book', n: 'address book', t: 'course', d: 'will assign books by...'},
        {c: 'far fa-newspaper', n: 'newspaper', t: 'piece', d: 'appeared in an edited periodical'},
        {c: 'far fa-file-word', n: 'sheet of paper', t: 'piece', d: 'was published as an independent essay'},
        {c: 'fas fa-dice', n: 'pair of dice', t: 'link', d: 'will take you somewhere random'},
        {c: 'fas fa-dharmachakra', n: 'Dharma Wheel', t: 'piece', d: 'is canonical'},
        {c: 'fas fa-volume-up', n: 'speaker', t: 'piece', d: 'is meant to be listened to'},
        {c: 'fas fa-book-open', n: 'open book', t: 'piece', d: 'is a self-published, open-access book(let)'},
        {c: 'fas fa-music', n: 'pair of eighth-notes', t: 'piece', d: 'is musical'},
        {c: 'fas fa-film', n: 'film strip', t: 'piece', d: 'is meant to be watched'},
        {c: 'fas fa-video', n: 'projector', t: 'link', d: 'takes you to a video'},
        {c: 'fas fa-podcast', n: 'radio antenna', t: 'piece', d: 'can be found on any podcast app'},
        {c: 'fas fa-graduation-cap', n: 'graduation cap', t: 'piece', d: 'is an unedited, academic thesis'},
        {c: 'far fa-pen-to-square', n: 'pencil in a square', t: 'piece', d: 'is a comic'},
        {c: 'fas fa-feather', n: 'rounded feather', t: 'piece', d: 'is a work of fiction'},
        {c: 'fas fa-vihara', n: 'pagoda', t: 'course', d: 'is about Buddhism as a cultural institution'},
        {c: 'far fa-map fa-rotate-90', n: 'folded scroll', t: 'course', d: 'will cover old, Buddhist texts'},
        {c: 'fas fa-chalkboard-teacher', n: 'lecturer', t: 'course', d: 'is a structured series of classes'},
        {c: 'fas fa-cloud-arrow-down', n: 'cloud downarrow icon', t: 'link', d: 'downloads from the cloud'},
        {c: 'fab fa-google-drive', n: 'triangular logo', t: 'link', d: 'will open in Google Drive'},
        {c: 'fas fa-tablet-alt', n: 'tablet', t: 'link', d: 'will download an eBook file suitable for tablets and ereaders'},
        {c: 'fab fa-google-play', n: 'triangular icon', t: 'link', d: 'will open in Google Play'},
        {c: 'fas fa-file-pdf', n: 'dark PDF file icon', t: 'link', d: 'takes you directly to the PDF File on a different website'},
        {c: 'fas fa-route', n: 'path icon', t: 'link', d: 'points to the original version of the piece'},
        {c: 'fab fa-youtube', n: 'video icon', t: 'link', d: 'will open in YouTube'},
        {c: 'fas fa-file-audio', n: 'dark audio file icon', t: 'link', d: 'takes you directly to the audio file on a different website'},
        {c: 'fas fa-globe', n: 'globe', t: 'link', d: 'will take you off to another website on the World Wide Web'},
        {c: 'fas fa-book-reader', n: 'sphere rising from an open book', t: 'piece', d: 'is an excerpt from a book'},
        {c: 'fas fa-feather-alt', n: 'pointy feather', t: 'piece', d: 'is ~poetic~'},
        {c: 'far fa-file-powerpoint', n: 'sheet of paper with a &quot;P&quot; on it', t: 'piece', d: 'was published in an edited volume'},
        {c: 'fas fa-atlas', n: 'book with a globe on it', t: 'piece', d: 'is reference material'},
        {c: 'fas fa-image', n: 'picture', t: 'course', d: 'is about imagery'},
        {c: 'fas fa-crow', n: 'bird', t: 'course', d: 'is beautiful and rare but requires patient attentiveness'},
        {c: 'fas fa-hand-holding', n: 'hand resting palm-up', t: 'course', d: 'is about the Buddha\'s generosity, renunciation, meditation, and wisdom'},
        {c: 'fas fa-chess-queen', n: 'chess queen', t: 'course', d: 'is ~intellectual~'},
        {c: 'fab fa-pagelines', n: 'young, upward-turning branch', t: 'course', d: 'is about spiritual growth'},
        {c: 'fas fa-dove', n: 'bird in flight', t: 'course', d: 'is the sequel to the MN course'},
        {c: 'fas fa-spinner', n: 'arrangement of seven dots', t: 'course', d: 'will cover the seventh chapter of the MA and how to fill in the last step of the Noble Eightfold Path'},
        {c: 'far fa-heart', n: 'empty heart', t: 'course', d: 'is about the paradoxical nature of nirvana'},
        {c: 'fas fa-cloud-sun', n: 'sun coming out from behind the clouds', t: 'course', d: 'will dazzle you with its brilliance'},
        {c: 'fas fa-parking', n: 'P in a square', t: 'course', d: 'is about the Pali Language'},
        {c: 'fab fa-product-hunt', n: 'P in a circle', t: 'course', d: 'is the sequel to Pali Level 1'},
        {c: 'fac-fojing', n: 'Chinese word', t: 'course', d: 'is about Buddhist texts in Chinese'},
        {c: 'fas fa-mountain', n: 'mountain', t: 'course', d: 'is about the spiritual path and its pinnacle'},
        {c: 'fas fa-cable-car', n: 'gondola', t: 'course', d: 'is a quick and easy way up to the Tibetan language'},
        {c: 'fas fa-street-view', n: 'person in a circle', t: 'course', d: 'is about the Pure Land and its context'},
        {c: 'fas fa-person-circle-exclamation', n: 'person with an exclamation mark', t: 'course', d: 'is about how humans respond to their environment'}
    ]
    @@operations = @@icons.map { |icon| {regex: Regexp.new('<i class="'+icon[:c]+'"'), longreplacement: '<i aria-hidden="true" title="This '+icon[:n]+' lets you know that the '+icon[:t]+' '+icon[:d]+'." class="'+icon[:c]+'"', replacement: '<i aria-hidden="true" title="'+icon[:d]+'" class="'+icon[:c]+'"'} }
    def addicontips(inp)
      ret = inp
      for icon in @@operations
        ret = ret.gsub(icon[:regex], icon[:replacement])
      end
      return ret
    end
  end
end

Liquid::Template.register_filter(Jekyll::IconTipFilter)

